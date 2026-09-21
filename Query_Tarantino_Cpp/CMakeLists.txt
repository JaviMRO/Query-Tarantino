cmake_minimum_required(VERSION 3.20)
project(QueryTarantinoStage1 CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(SQLite3 REQUIRED)
find_package(nlohmann_json REQUIRED)
find_package(mongocxx REQUIRED)
find_package(bsoncxx REQUIRED)
find_package(CURL REQUIRED)

add_executable(stage1
    src/domain/tokenizer.cpp
    src/domain/header_parser.cpp
    src/application/control_pipeline.cpp
    src/application/ingest_book_use_case.cpp
    src/infrastructure/datalake/time_based_adapter.cpp
    src/infrastructure/datalake/book_based_adapter.cpp
    src/infrastructure/datalake/batch_based_adapter.cpp
    src/infrastructure/metadata/sqlite_metadata_adapter.cpp
    src/infrastructure/control/file_control_state_store.cpp
    src/infrastructure/index/monolithic_json_adapter.cpp
    src/infrastructure/index/mongodb_index_adapter.cpp
    src/infrastructure/index/hierarchical_folder_adapter.cpp
    src/infrastructure/downloader/gutenberg_http_downloader.cpp
)

target_include_directories(stage1 PRIVATE src)

target_link_libraries(stage1
    PRIVATE
        SQLite::SQLite3
        nlohmann_json::nlohmann_json
        mongo::mongocxx_shared
        mongo::bsoncxx_shared
        CURL::libcurl
)
