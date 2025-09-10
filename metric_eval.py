import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.firefox import GeckoDriverManager
from bs4 import BeautifulSoup


firefoxOptions = Options()
firefoxOptions.add_argument("--headless")
firefoxOptions.add_argument("--no-sandbox")
firefoxOptions.add_argument("--disable-dev-shm-usage")

service = Service(GeckoDriverManager().install())


class metric_eval:
    def __init__(self, data_url):
        self.data_url = data_url
        # Initialize driver once
        self.driver = webdriver.Firefox(options=firefoxOptions, service=service)
        self.driver.implicitly_wait(2)  # short dynamic wait

    def calculate_metrics(self, flag='Accuracy'):
        df = pd.read_csv(self.data_url)
        pred_movies = df['Title'].tolist()

        successful_movies = []
        unsuccessful_movies = []
        final_results = {}

        for mov in pred_movies:
            try:
                print(f"Started for movie {mov}")
                url = f"https://www.youtube.com/@VKunia/search?query={mov.replace(' ','%20')}"
                self.driver.get(url)

                # wait up to 2s for a video to appear
                WebDriverWait(self.driver, 2).until(
                    EC.presence_of_element_located((By.TAG_NAME, "ytd-video-renderer"))
                )

                soup = BeautifulSoup(self.driver.page_source, "html.parser")
                videos = soup.find_all("ytd-video-renderer")

                found = False
                for v in videos[:2]:
                    title_tag = v.find("a", id="video-title")
                    metadata = v.find("div", id="metadata-line")
                    if not title_tag or not metadata:
                        continue

                    title = title_tag.get("title", "").lower()
                    if "teaser" in title or "trailer" in title:
                        continue
                    if mov.lower() not in title:
                        continue

                    spans = metadata.find_all("span")
                    if not spans:
                        continue
                    views = spans[0].get_text(strip=True)

                    # normalize views
                    if "K" in views:
                        views_val = float(views.replace("K views", "").strip()) * 1000
                    elif "M" in views:
                        views_val = float(views.replace("M views", "").strip()) * 1_000_000
                    else:
                        views_val = float(views.replace("views", "").strip().replace(",", ""))

                    min_views = df.loc[df['Title'] == mov, 'Min'].values[0]
                    max_views = df.loc[df['Title'] == mov, 'Max'].values[0]
                    min_views_val = float(str(min_views).replace("k", "")) * 1000
                    max_views_val = float(str(max_views).replace("k", "")) * 1000

                    if flag == 'Accuracy':
                        if views_val >= min_views_val:
                            successful_movies.append(mov)
                            print(f"{mov} ✓ Accurate")
                        else:
                            unsuccessful_movies.append(mov)
                            print(f"{mov} ✗ Not Accurate")
                    elif flag == 'Precision':
                        if min_views_val <= views_val <= max_views_val:
                            successful_movies.append(mov)
                            print(f"{mov} ✓ Precise")
                        else:
                            unsuccessful_movies.append(mov)
                            print(f"{mov} ✗ Not Precise")

                    found = True
                    break

                if not found:
                    unsuccessful_movies.append(mov)

            except Exception as e:
                print(f"Error processing {mov}: {e}")
                unsuccessful_movies.append(mov)

        # Quit driver once
        self.driver.quit()

        # final results
        final_results['successful_movies'] = successful_movies
        final_results['unsuccessful_movies'] = unsuccessful_movies
        final_results['accuracy'] = len(successful_movies) / max(1, (len(successful_movies) + len(unsuccessful_movies)))

        return final_results


if __name__ == '__main__':
    me = metric_eval('User/vkunia/vkunia_cache.csv')
    print(me.calculate_metrics())
