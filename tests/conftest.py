"""Shared test setup: tests use keyword search only, so they never download the embedding model."""
import os

os.environ["EMBED_MODEL"] = ""
