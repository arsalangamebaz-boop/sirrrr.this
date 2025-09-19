# hashtags.py
import random
from pytrends.request import TrendReq

def get_trending_hashtags():
    """
    Fetch trending hashtags using Google Trends.
    Falls back to a static global list if unavailable.
    """
    try:
        pytrends = TrendReq(hl="en-US", tz=360)
        pytrends.build_payload(kw_list=["Instagram", "TikTok", "Reels"])
        trends = pytrends.trending_searches(pn="united_states")

        # take top 20 and convert to hashtags
        trending = [f"#{t.replace(' ', '')}" for t in trends[0].tolist()[:20]]
        if trending:
            print("✅ Got trending hashtags from pytrends")
            return trending
    except Exception as e:
        print("⚠️ Pytrends failed, using fallback hashtags:", e)

    # --- Fallback list: popular global hashtags ---
    fallback = [
        "#love", "#instagood", "#fashion", "#photooftheday", "#beautiful",
        "#art", "#photography", "#happy", "#picoftheday", "#follow",
        "#selfie", "#summer", "#reels", "#explorepage", "#instadaily",
        "#style", "#smile", "#like4like", "#music", "#friends",
        "#travel", "#fitness", "#life", "#beauty", "#motivation",
        "#viral", "#funny", "#tiktok", "#trend", "#instagram"
    ]

    # randomize fallback list a bit each run
    return random.sample(fallback, 20)
