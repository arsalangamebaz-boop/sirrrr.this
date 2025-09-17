from pytrends.request import TrendReq

def get_trending_hashtags():
    try:
        pytrends = TrendReq(hl='en-US', tz=360)
        pytrends.build_payload(kw_list=["instagram"])
        trending = pytrends.trending_searches(pn='pakistan')
        hashtags = ["#" + tag.replace(" ", "") for tag in trending[0].head(10).tolist()]
        return hashtags
    except Exception as e:
        print("⚠️ Pytrends failed, using fallback hashtags:", e)
        return [
            "#instagood", "#photooftheday", "#love", "#fashion", 
            "#beautiful", "#happy", "#art", "#picoftheday", "#style", "#followme"
        ]
