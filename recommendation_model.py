
from collections import defaultdict

from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.metrics.pairwise import cosine_similarity

from database import get_connection


class GameRecommender:

    def __init__(self):
        self.games = {}
        self.features = defaultdict(list)

        self.encoder = MultiLabelBinarizer(
            sparse_output=True
        )

        self.transformer = TfidfTransformer()

        self.matrix = None
        self.appids = []

    
    def load_data(self):

        conn = get_connection()

        try:
            with conn.cursor() as cursor:

                cursor.execute(
                    "SELECT appid, name FROM games"
                )

                for appid, name in cursor.fetchall():
                    self.games[str(appid)] = name

                cursor.execute(
                    "SELECT appid, category FROM game_tags"
                )

                for appid, category in cursor.fetchall():

                    appid = str(appid)

                    if appid in self.games and category:
                        self.features[appid].append(category)

        finally:
            conn.close()

        self.appids = [
            appid for appid in self.games
            if self.features[appid]
        ]

        if not self.appids:
            raise ValueError(
                "No games with features found in PostgreSQL"
            )

        feature_lists = [
            self.features[appid]
            for appid in self.appids
        ]

        binary_matrix = self.encoder.fit_transform(
            feature_lists
        )

        self.matrix = self.transformer.fit_transform(
            binary_matrix
        )

    
    def recommend(self, favorite_appids, top_n=10):

        if self.matrix is None:
            raise ValueError("Call load_data() first")

        favorites = [
            str(appid) for appid in favorite_appids
        ]

        known = [
            appid for appid in favorites
            if appid in self.appids
        ]

        if not known:
            raise ValueError(
                "None of the selected games have features"
            )

        positions = {
            appid: i
            for i, appid in enumerate(self.appids)
        }

        favorite_rows = [
            positions[appid] for appid in known
        ]

        # Calculate a user's preference vector
        user_vector = self.matrix[favorite_rows].mean(
            axis=0
        )

        # Compare that vector with every game
        import numpy as np

        scores = cosine_similarity(
            np.asarray(user_vector),
            self.matrix
        )[0]

        # Exclude selected favorites
        for appid in set(favorites):
            if appid in positions:
                scores[positions[appid]] = -1

        best_indices = scores.argsort()[::-1][:top_n]

        recommendations = []

        for i in best_indices:

            if scores[i] <= 0:
                continue

            appid = self.appids[i]

            recommendations.append({
                "appid": appid,
                "name": self.games[appid],
                "similarity": round(float(scores[i]), 4)
            })

        return recommendations


    
