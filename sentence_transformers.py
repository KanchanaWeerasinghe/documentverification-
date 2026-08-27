class SentenceTransformer:
    def __init__(self, model_name=None):
        self.model_name = model_name

    def encode(self, texts, show_progress_bar=False):
        # Return a deterministic small vector for each text to allow tests to run
        return [[0.01] * 384 for _ in texts]
