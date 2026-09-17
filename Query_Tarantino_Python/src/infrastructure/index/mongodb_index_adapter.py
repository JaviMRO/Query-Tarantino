"""
TODO: Implementacion de InvertedIndexStorage que guarda el indice invertido
en una coleccion MongoDB con un documento por termino.
"""

from pymongo import MongoClient

from src.domain.ports import InvertedIndexStorage


class MongoDbIndexAdapter:
    pass  # TODO: implementar metodos de InvertedIndexStorage usando pymongo
