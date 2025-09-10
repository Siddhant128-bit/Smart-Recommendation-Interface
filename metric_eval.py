import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

class MetricEval:
    def __init__(self, data_url, executable_path=None):
        """
        Initialize with a CSV path and optional Selenium ChromeDriver service.
        If driver_service is None, a default headless Chrome setup is used.
        """
        self.data_url = data_url
        if executable_path ==None:
            self.driver_service = None
        else:
            self.driver_service = Service(executable_path=executable_path)
        self.options = Options()
        self.options.add_argument("--headless=new")
        self.options.add_argument("--no-sandbox")
        self.options.add_argument("--disable-dev-shm-usage")
        self.options.add_argument("--disable-gpu")  # Extra for cloud stability
        self.options.add_argument("--remote-debugging-port=9222")  # For containerized envs

    def calculate_metrics(self, flag='Accuracy'):
        df = pd.read_csv(self.data_url)
        pred_movies = df['Title'].tolist()

        successful_movies = []
        unsuccessful_movies = []
        final_results = {}

        for mov in pred_movies:
            print(f"Started for movie {mov}")
            url = f"https://www.youtube.com/@VKunia/search?query={mov.replace(' ', '%20')}"

            # Initialize driver with provided service or default
            driver = webdriver.Chrome(
                service=self.driver_service,
                options=self.options
            )
            driver.get(url)

            try:
                # Wait until at least one video appears
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "ytd-video-renderer"))
                )
                html = driver.page_source
                soup = BeautifulSoup(html, "html.parser")

                videos = soup.find_all("ytd-video-renderer")
                found_match = False

                for v in videos[:3]:  # Check first 3 for better coverage
                    title_tag = v.find("a", id="video-title")
                    metadata = v.find("div", id="metadata-line")

                    views = None
                    if metadata:
                        spans = metadata.find_all("span")
                        if spans:
                            views = spans[0].get_text(strip=True)  # e.g., "21K views"

                    if title_tag and title_tag.has_attr("title"):
                        video_title = title_tag['title'].lower()
                        if 'teaser' in video_title or 'trailer' in video_title:
                            continue
                        elif mov.lower() in video_title:
                            found_match = True
                            # Normalize views
                            if views:
                                views = views.lower().replace(" views", "").replace("view", "").replace(",", "")
                                if "k" in views:
                                    views_val = float(views.replace("k", "").strip()) * 1000
                                elif "m" in views:
                                    views_val = float(views.replace("m", "").strip()) * 1_000_000
                                elif "b" in views:
                                    views_val = float(views.replace("b", "").strip()) * 1_000_000_000
                                else:
                                    views_val = float(views.strip())
                            else:
                                views_val = 0  # Default if no views

                            min_views = df.loc[df['Title'] == mov, 'Min'].values[0]
                            max_views = df.loc[df['Title'] == mov, 'Max'].values[0]

                            # Normalize min/max (handle 'k' suffix)
                            min_views_val = float(str(min_views).lower().replace("k", "")) * 1000 if "k" in str(min_views).lower() else float(min_views)
                            max_views_val = float(str(max_views).lower().replace("k", "")) * 1000 if "k" in str(max_views).lower() else float(max_views)

                            if flag == 'Accuracy':
                                if views_val >= min_views_val:
                                    successful_movies.append(mov)
                                    print(f"{mov} noted successfully -----")
                                else:
                                    unsuccessful_movies.append(mov)
                                    print(f"{mov} noted not accurate -----")
                            elif flag == 'Precision':
                                if min_views_val <= views_val <= max_views_val:
                                    successful_movies.append(mov)
                                    print(f"{mov} noted successfully -----")
                                else:
                                    unsuccessful_movies.append(mov)
                                    print(f"{mov} noted not precise -----")
                            break  # Stop after first match

                if not found_match:
                    print(f"No matching video found for {mov}")

            except Exception as e:
                print(f"Error processing {mov}: {str(e)}")
                
            finally:
                driver.quit()

        # Final results
        total = len(successful_movies) + len(unsuccessful_movies)
        final_results['successful_movies'] = successful_movies
        final_results['unsuccessful_movies'] = unsuccessful_movies
        final_results['accuracy'] = len(successful_movies) / max(1, total)

        return final_results

if __name__ == '__main__':
    # For local testing
    me = MetricEval('User/vkunia/vkunia_cache.csv')
    results = me.calculate_metrics(flag='Precision')
    print(results)