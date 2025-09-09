import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
options = Options()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")


class metric_eval:
    def __init__(self,data_url):
        self.data_url=data_url
    
    def calculate_metrics(self,flag='Accuracy'):
        df = pd.read_csv(self.data_url)
        pred_movies = df['Title'].tolist()

        successful_movies = []
        unsuccessful_movies = []
        final_results = {}

        for mov in pred_movies:
            print(f"Started for movie {mov}")
            url = f"https://www.youtube.com/@VKunia/search?query={mov.replace(' ','%20')}"

            
            driver = webdriver.Chrome(options=options)
            driver.get(url)

            try:
                # wait until at least one video appears
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.TAG_NAME, "ytd-video-renderer"))
                )
                html = driver.page_source
                soup = BeautifulSoup(html, "html.parser")

                videos = soup.find_all("ytd-video-renderer")

                for v in videos[:2]:  # check first 2
                    title_tag = v.find("a", id="video-title")
                    metadata = v.find("div", id="metadata-line")

                    views = None
                    if metadata:
                        spans = metadata.find_all("span")
                        if spans:
                            views = spans[0].get_text(strip=True)  # e.g. "21K views"

                    if title_tag and title_tag.has_attr("title"):
                        if 'teaser' in title_tag['title'].lower() or 'trailer' in title_tag['title'].lower():
                            continue
                        elif mov.lower() in title_tag['title'].lower():
                            # normalize views
                            if "K" in views:
                                views_val = float(views.replace("K views", "").strip()) * 1000
                            elif "M" in views:
                                views_val = float(views.replace("M views", "").strip()) * 1_000_000
                            else:
                                views_val = float(views.replace("views", "").strip().replace(",", ""))

                            min_views = df.loc[df['Title'] == mov, 'Min'].values[0]
                            max_views = df.loc[df['Title'] == mov, 'Max'].values[0]

                            # remove "k" if present
                            min_views_val = float(str(min_views).replace("k", "")) * 1000
                            max_views_val = float(str(max_views).replace("k", "")) * 1000
                            
                            if flag=='Accuracy':
                                if views_val >= min_views_val:
                                    successful_movies.append(mov)
                                    print(f"{mov} noted successfully -----")
                                else:
                                    unsuccessful_movies.append(mov)
                                    print(f"{mov} noted not accurate -----")
                            elif flag=='Precision':
                                if views_val >= min_views_val and views_val<=max_views_val:
                                    successful_movies.append(mov)
                                    print(f"{mov} noted successfully -----")
                                else:
                                    unsuccessful_movies.append(mov)
                                    print(f"{mov} noted not precise -----")
            except Exception as e:
                print(f"Error processing {mov}")
            finally:
                driver.quit()   

        # final results
        final_results['successful_movies'] = successful_movies
        final_results['unsuccessful_movies'] = unsuccessful_movies
        final_results['accuracy'] = len(successful_movies) / max(1, (len(successful_movies)+len(unsuccessful_movies)))

        return final_results

if __name__=='__main__':
    me=metric_eval('User/vkunia/vkunia_cache.csv')
    me.calculate_metrics()