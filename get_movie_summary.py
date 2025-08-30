import imdb
from sentence_transformers import SentenceTransformer
import synopsis_gen as sgen

# Create IMDb and SentenceTransformer once
ia = imdb.IMDb()
embedder = SentenceTransformer("all-MiniLM-L6-v2")

def get_movie_synopsis_embedding(movie_name,embedder):
    """
    Returns a tuple -> (synopsis_text, embedding_vector)
    """
    print(f'Fetching movie synopsis for {movie_name}...')
    try:
        results = ia.search_movie(movie_name)
        if not results:
            return None, None

        movie = results[0]

        # Only request the synopsis info (faster than full update)
        ia.update(movie, info=['synopsis'])

        synopsis_list = movie.get('synopsis', [])
        if not synopsis_list:
            synopsis_list=[sgen.ask_gemini(f'Give me synopsis of this movie or series under 25 lines, Just give me the snyposis nothing else: {movie_name}')]

        synopsis = synopsis_list[0]

        # Create embedding
        embedding = embedder.encode(synopsis)
        print(f'Synopsis for {movie_name} fetched successfully.')
        print('##'*20)
        return embedding

    except Exception as e:
        print( f"An error occurred: {e}")
        return 'Delete this !'

#get movie summary short one from gemini 
def get_movie_summary_embedding(movie_name,embedder):
    try:
        summary_list=[sgen.ask_gemini(f'Give me summary of this movie or series under 3 sentences, Concate genre names as you see fit according to your understanding,Just give me the summary and genre nothing else: {movie_name}')]

        summary = summary_list[0]

        # Create embedding
        embedding = embedder.encode(summary)
        print(f'Summary for {movie_name} fetched successfully. ')
        print('#'*20)
        return embedding
    
    except Exception as e: 
        print(f' An error occured {e}')
        return "Delete this !"

# Example usage
if __name__ == "__main__":
    # movie_name = input("Enter the movie name: ")
    movie_name='Now You See Me'  # Example movie name
    synopsis_embedding = get_movie_summary_embedding(movie_name,embedder)

    if synopsis_embedding is not None:
        print("\nEmbedding vector (first 5 values):")
        print(synopsis_embedding[:5])
