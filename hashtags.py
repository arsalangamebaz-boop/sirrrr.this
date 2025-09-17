# hashtags.py
import random
from pytrends.request import TrendReq

FALLBACK_TAGS = [
    "instagood","photooftheday","fashion","beautiful","happy","cute","followme",
    "picoftheday","art","nature","style","travel","fitness","love","music",
    "motivation","life","inspiration","friends","explore"
]

def fetch_trending_from_google():
    pytrends = TrendReq(hl='en-US', tz=360)
    # get today trending searches globally
    df = pytrends.trending_searches(pn="united_states")
    tags = df[0].tolist()
    hashtags = [t.replace(" ", "") for t in tags]
    return hashtags[:30]

def get_trending_hashtags():
    try:
        tags = fetch_trending_from_google()
        if tags:
            return [t.lower() for t in tags]
    except Exception:
        pass
    tmp = FALLBACK_TAGS.copy()
    random.shuffle(tmp)
    return tmp
