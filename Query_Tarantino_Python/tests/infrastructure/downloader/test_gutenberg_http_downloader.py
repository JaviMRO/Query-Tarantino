import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import requests

from src.domain.model import BookText, DownloadException, FailureReason
from src.infrastructure.downloader.gutenberg_http_downloader import GutenbergHttpDownloader

BOOK_ID = 2701
FIRST_PATH = "/cache/epub/2701/pg2701.txt"
SECOND_PATH = "/files/2701/2701-0.txt"
THIRD_PATH = "/files/2701/2701.txt"
RAW_TEXT = (
    b"Title: Moby Dick\r\n"
    b"\r\n"
    b"*** START OF THE PROJECT GUTENBERG EBOOK MOBY DICK ***\r\n"
    b"Call me Ishmael.\r\n"
    b"*** END OF THE PROJECT GUTENBERG EBOOK MOBY DICK ***\r\n"
    b"License text"
)
SERVER_POLL_SECONDS = 0.01
SECONDS_BETWEEN_REQUESTS = 1.0
EXPECTED_TEXT = BookText("Title: Moby Dick", "Call me Ishmael.")


@dataclass
class Route:
    status: int = 200
    body: bytes = b""
    location: str = ""
    cuts_connection: bool = False


@dataclass
class GutenbergStub:
    base_url: str = ""
    routes: dict[str, Route] = field(default_factory=dict)
    requested_paths: list[str] = field(default_factory=list)
    user_agents: list[str] = field(default_factory=list)


class FakeTime:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def handler_for(stub: GutenbergStub) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            stub.requested_paths.append(self.path)
            stub.user_agents.append(self.headers.get("User-Agent", ""))
            route = stub.routes.get(self.path, Route(status=404))
            if route.cuts_connection:
                self.close_connection = True
                return
            self.send_response(route.status)
            if route.location:
                self.send_header("Location", route.location)
            self.send_header("Content-Length", str(len(route.body)))
            self.end_headers()
            self.wfile.write(route.body)

        def log_message(self, format: str, *args: object) -> None:
            pass

    return Handler


@pytest.fixture
def stub() -> Iterator[GutenbergStub]:
    gutenberg = GutenbergStub()
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(gutenberg))
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": SERVER_POLL_SECONDS}, daemon=True).start()
    gutenberg.base_url = f"http://127.0.0.1:{server.server_port}"
    yield gutenberg
    server.shutdown()
    server.server_close()


@pytest.fixture
def session() -> Iterator[requests.Session]:
    with requests.Session() as http_session:
        yield http_session


def build(stub: GutenbergStub, session: requests.Session, fake_time: FakeTime | None = None) -> GutenbergHttpDownloader:
    clock = fake_time or FakeTime()
    return GutenbergHttpDownloader(session, stub.base_url, clock.monotonic, clock.sleep, SECONDS_BETWEEN_REQUESTS)


def test_first_url_success_downloads_decodes_and_splits(stub: GutenbergStub, session: requests.Session) -> None:
    stub.routes[FIRST_PATH] = Route(body=RAW_TEXT)

    result = build(stub, session).download(BOOK_ID)

    assert result == EXPECTED_TEXT
    assert stub.requested_paths == [FIRST_PATH]


def test_falls_back_to_the_second_url_on_404(stub: GutenbergStub, session: requests.Session) -> None:
    stub.routes[SECOND_PATH] = Route(body=RAW_TEXT)

    result = build(stub, session).download(BOOK_ID)

    assert result == EXPECTED_TEXT
    assert stub.requested_paths == [FIRST_PATH, SECOND_PATH]


def test_all_three_urls_failing_raises_http_error(stub: GutenbergStub, session: requests.Session) -> None:
    with pytest.raises(DownloadException) as raised:
        build(stub, session).download(BOOK_ID)

    assert raised.value.reason == FailureReason.HTTP_ERROR
    assert stub.requested_paths == [FIRST_PATH, SECOND_PATH, THIRD_PATH]


def test_a_cut_connection_counts_as_a_failed_url(stub: GutenbergStub, session: requests.Session) -> None:
    stub.routes[FIRST_PATH] = Route(cuts_connection=True)
    stub.routes[SECOND_PATH] = Route(body=RAW_TEXT)

    assert build(stub, session).download(BOOK_ID) == EXPECTED_TEXT


def test_an_unreachable_server_raises_http_error(session: requests.Session) -> None:
    fake_time = FakeTime()
    downloader = GutenbergHttpDownloader(
        session, "http://127.0.0.1:9", fake_time.monotonic, fake_time.sleep, SECONDS_BETWEEN_REQUESTS
    )

    with pytest.raises(DownloadException) as raised:
        downloader.download(BOOK_ID)

    assert raised.value.reason == FailureReason.HTTP_ERROR


def test_redirects_are_followed(stub: GutenbergStub, session: requests.Session) -> None:
    stub.routes[FIRST_PATH] = Route(status=302, location="/moved/pg2701.txt")
    stub.routes["/moved/pg2701.txt"] = Route(body=RAW_TEXT)

    assert build(stub, session).download(BOOK_ID) == EXPECTED_TEXT


def test_every_request_sends_the_spec_user_agent(stub: GutenbergStub, session: requests.Session) -> None:
    stub.routes[SECOND_PATH] = Route(body=RAW_TEXT)

    build(stub, session).download(BOOK_ID)

    assert stub.user_agents == ["QueryTarantino/1.0 (ULPGC Big Data student project)"] * 2


def test_waits_one_second_between_the_starts_of_fallback_requests(
    stub: GutenbergStub, session: requests.Session
) -> None:
    stub.routes[THIRD_PATH] = Route(body=RAW_TEXT)
    fake_time = FakeTime()

    build(stub, session, fake_time).download(BOOK_ID)

    assert fake_time.sleeps == [1.0, 1.0]


def test_waits_only_the_rest_of_the_second_between_books(stub: GutenbergStub, session: requests.Session) -> None:
    stub.routes[FIRST_PATH] = Route(body=RAW_TEXT)
    fake_time = FakeTime()
    downloader = build(stub, session, fake_time)
    downloader.download(BOOK_ID)
    fake_time.now += 0.25

    downloader.download(BOOK_ID)

    assert fake_time.sleeps == [0.75]


def test_does_not_wait_when_a_second_has_already_passed(stub: GutenbergStub, session: requests.Session) -> None:
    stub.routes[FIRST_PATH] = Route(body=RAW_TEXT)
    fake_time = FakeTime()
    downloader = build(stub, session, fake_time)
    downloader.download(BOOK_ID)
    fake_time.now += 2.0

    downloader.download(BOOK_ID)

    assert fake_time.sleeps == []


def test_missing_markers_propagates_as_no_markers(stub: GutenbergStub, session: requests.Session) -> None:
    stub.routes[FIRST_PATH] = Route(body=b"no markers in this text")

    with pytest.raises(DownloadException) as raised:
        build(stub, session).download(BOOK_ID)

    assert raised.value.reason == FailureReason.NO_MARKERS


def test_empty_body_propagates_as_empty_body(stub: GutenbergStub, session: requests.Session) -> None:
    stub.routes[FIRST_PATH] = Route(
        body=b"*** START OF THE PROJECT GUTENBERG EBOOK X ***\n \n*** END OF THE PROJECT GUTENBERG EBOOK X ***"
    )

    with pytest.raises(DownloadException) as raised:
        build(stub, session).download(BOOK_ID)

    assert raised.value.reason == FailureReason.EMPTY_BODY


def test_invalid_utf8_is_decoded_as_latin1_without_bom(stub: GutenbergStub, session: requests.Session) -> None:
    stub.routes[FIRST_PATH] = Route(body=RAW_TEXT.replace(b"Ishmael", b"Isma\xebl"))

    result = build(stub, session).download(BOOK_ID)

    assert result.body == "Call me Ismaël."


def test_fetch_text_returns_the_whole_normalized_text_without_splitting(
    stub: GutenbergStub, session: requests.Session
) -> None:
    stub.routes[FIRST_PATH] = Route(body=b"\xef\xbb\xbf" + RAW_TEXT)

    text = build(stub, session).fetch_text(BOOK_ID)

    assert text == RAW_TEXT.decode("utf-8").replace("\r\n", "\n")


def test_a_longer_wait_between_requests_can_be_configured(stub: GutenbergStub, session: requests.Session) -> None:
    stub.routes[SECOND_PATH] = Route(body=RAW_TEXT)
    fake_time = FakeTime()
    downloader = GutenbergHttpDownloader(session, stub.base_url, fake_time.monotonic, fake_time.sleep, 2.0)

    downloader.download(BOOK_ID)

    assert fake_time.sleeps == [2.0]


def test_a_wait_below_one_second_is_rejected(session: requests.Session) -> None:
    fake_time = FakeTime()

    with pytest.raises(ValueError):
        GutenbergHttpDownloader(session, "http://127.0.0.1:9", fake_time.monotonic, fake_time.sleep, 0.5)
