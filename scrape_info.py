from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time
import pandas as pd

# Set up Chrome options for headless mode
chrome_options = Options()
# chrome_options.add_argument('--headless')  # Uncomment to run in headless mode
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')
chrome_options.add_argument('--disable-gpu')
chrome_options.add_argument('--remote-debugging-port=9222')
chrome_options.add_argument('--window-size=1920x1080')

# Specify the path to the ChromeDriver executable
service = Service(None)

# Initialize the WebDriver
driver = webdriver.Chrome(service=service, options=chrome_options)
# Function to convert abbreviated counts (e.g., 'K', 'M') to full numbers
def convert_abbreviated_count(count):
    # count=count.replace('.','')
    if 'K' in count:
        # print((count.replace('K', '').strip()))
        return float(count.replace('K', '').strip()) * 1000
    elif 'M' in count:
        return float(count.replace('M', '').strip()) * 1000000
    return float(count.replace(',',''))

# Function to extract video details (title, URL, and views)
def get_video_details():
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    # Find all video containers
    videos = soup.find_all('ytd-rich-grid-media')
    # print(videos)
    video_details = []
    
    for video in videos:
        # print(video)
        try:
            title_tag = video.find('yt-formatted-string', {'id': 'video-title'})
            title_tag=str(title_tag)
            title_tag=title_tag.split('>')[1].split('<')[0]
            url_tag = video.find('a', {'id': 'video-title-link'})
            view_tag=video.find('span', {'class': 'inline-metadata-item style-scope ytd-video-meta-block'})
            view_tag=str(view_tag)
            view_tag=view_tag.split('views')[0].split('>')[-1]
            view_tag=convert_abbreviated_count(view_tag)
            video_details.append({
                'title': title_tag,
                'views': view_tag
            })
        except Exception as e:
            print(e)

    return video_details

# Function to scroll the page
def scroll_page(video_url="https://www.youtube.com/@VKunia/videos",channel='other_channel'):
    driver.get(video_url)
    if channel=='other_channel':
        time.sleep(1.5)  # Allow the page to load
        last_height = driver.execute_script("return document.documentElement.scrollHeight")
        
        while True:
            driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
            time.sleep(1.5)  # Allow more videos to load
            new_height = driver.execute_script("return document.documentElement.scrollHeight")
            if new_height == last_height:
                break
            
            last_height = new_height
    else:
        time.sleep(1.05)
        last_height = driver.execute_script("return document.documentElement.scrollHeight")

# Function to extract the subscriber count
def get_subscriber_count():
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    # Find the element that contains the subscriber count
    subscriber_data = soup.find('div', class_='yt-page-header-view-model__page-header-headline-info')
    print(subscriber_data)
    if subscriber_data:
        subscriber_text = subscriber_data.get_text(strip=True)
        # Extract only the subscriber number, excluding additional text (like 'subscribers')
        if "subscribers" in subscriber_text:
            subscriber_count = subscriber_text.split(' subscribers')[0]
            return convert_abbreviated_count(subscriber_count.split('•')[1].strip())
    return None


if __name__=='__main__':
    our_channel="https://www.youtube.com/@VKunia/videos"
    scroll_page(our_channel,channel='our_channel')
    our_sub=get_subscriber_count()
    other_channels=[
        "https://www.youtube.com/@NatalieGoldReacts/videos",
        "https://www.youtube.com/@PopcornInBed/videos",
        "https://www.youtube.com/@alexhefnerstvmovievault/videos"
    ]
    detail_df=pd.DataFrame(columns=['Title','Views','Subscribers'])
    title=[]
    views=[]
    subscribers_l=[]

    for video_url in other_channels:
        print(video_url)
        # Run the scrolling function to load videos
        scroll_page(video_url=video_url)

        # Extract video details
        video_details = get_video_details()

        # Extract the total subscribers
        subscribers = get_subscriber_count()

        print(video_details)

        # # Print out the extracted details
        for detail in video_details:
            title.append(detail['title'])
            views.append(detail['views'])
            subscribers_l.append(subscribers)

    detail_df['Title']=title
    detail_df['Views']=views
    detail_df['Subscribers']=subscribers_l
    driver.quit()

    pd.set_option('display.max_columns', None)  # Show all columns
    pd.set_option('display.max_rows', None)     # Show all rows
    pd.set_option('display.max_colwidth', None) # Do not truncate column values

    elite_detail_df=detail_df.loc[detail_df['Views']/detail_df['Subscribers']>=0.85]
    elite_detail_df['est_views']=(elite_detail_df['Views']/elite_detail_df['Subscribers']*our_sub)/2
    