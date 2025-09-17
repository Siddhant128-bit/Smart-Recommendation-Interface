import pandas as pd
import re
from collections import defaultdict
import json

def sync_chatbot(username,good_movie_view_count=1000000,average_movie_view_count=50000,bad_movie_view_count=10000):

    final_results={}

    def check_view_level(view_count, good_view_count=good_movie_view_count, average_view_count=average_movie_view_count, bad_view_count=bad_movie_view_count):
        if view_count >= good_view_count:
            return (1, 0, 0)   # Good
        elif view_count >= average_view_count:
            return (0, 1, 0)   # Average
        elif view_count < bad_view_count:
            return (0, 0, 1)   # Bad
        return (0, 0, 0)       # Neutral (between avg & bad thresholds)

    data_test = pd.read_csv(f'User/{username}/{username}.csv')

    def calculate_metadata(grouped_data):
        meta_data = {}
        for key, group in grouped_data:
            results = group['Views'].apply(check_view_level)
            good = sum(r[0] for r in results)
            avg  = sum(r[1] for r in results)
            bad  = sum(r[2] for r in results)
            meta_data[key] = {"Total Good": good, "Total Average": avg, "Total Bad": bad}
        return meta_data


    meta_data_day = calculate_metadata(data_test.groupby("Video publish day"))

    def clean_and_split_genres(meta_by_genre):
        clean_meta = defaultdict(lambda: {"Total Good": 0, "Total Average": 0, "Total Bad": 0})

        for raw_genres, counts in meta_by_genre.items():
            # Remove markdown, bullets, numbers, extra symbols
            genres = re.split(r"[\n,\-\*\d\.\s]+", str(raw_genres))
            genres = [g.strip(" *:-.").title() for g in genres if g.strip()]

            for g in genres:
                clean_meta[g]["Total Good"] += counts["Total Good"]
                clean_meta[g]["Total Average"] += counts["Total Average"]
                clean_meta[g]["Total Bad"] += counts["Total Bad"]

        return dict(clean_meta)

    # Explode genres (handles multiple genres in one row)
    data_genre_split = data_test.copy()
    data_genre_split["genre"] = data_genre_split["genre"].astype(str).str.split(",")
    data_genre_split = data_genre_split.explode("genre")
    data_genre_split["genre"] = data_genre_split["genre"].str.strip()

    # Raw metadata by genre
    meta_data_genre_raw = calculate_metadata(data_genre_split.groupby("genre"))

    # Cleaned metadata
    meta_data_genre = clean_and_split_genres(meta_data_genre_raw)



    # ----------------------------
    # Results
    # ----------------------------
    meta_data_movies={}

    meta_data_movies['Good']=(data_test['Video title'].loc[data_test['Views'] >= good_movie_view_count]).tolist()
    meta_data_movies['Average']=(data_test['Video title'].loc[data_test['Views'] >= average_movie_view_count]).tolist()
    meta_data_movies['Bad']=(data_test['Video title'].loc[data_test['Views'] >= bad_movie_view_count]).tolist()


    # print("📅 Metadata by Day:\n", meta_data_day, "\n")
    # print("🎭 Metadata by Genre:\n", meta_data_genre)
    # print("🎬 Metadata by Movies:\n", meta_data_movies)

    final_results['By Day']=meta_data_day
    final_results['By Genre']=meta_data_genre
    final_results['By Movies']=meta_data_movies
    final_results['View Count Thresholds']={'Good':good_movie_view_count,'Average':average_movie_view_count,'Bad':bad_movie_view_count}
    with open(f'User/{username}/{username}_chatbot_metadata.json', 'w') as f:
        json.dump(final_results, f, indent=4)


if __name__=="__main__":
    sync_chatbot('vkunia')