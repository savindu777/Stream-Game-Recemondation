
from recommendation_model import GameRecommender

model = GameRecommender()

model.load_data()

print("Games with features:", len(model.appids))

recommendations = model.recommend(
    favorite_appids=["620"],
    top_n=5
)

for game in recommendations:
    print(game)
