import random


def generate(n: int, center: float, scale: float, seed: int = 0):
    for i in range(n):
        yield random.Random(seed + i).gauss(center, scale)
