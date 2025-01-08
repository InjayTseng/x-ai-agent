from database import TwitterDatabase
import json

def print_tweets():
    db = TwitterDatabase()
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT tweet_id, content, author, summary FROM tweets')
        tweets = cursor.fetchall()
        
        if not tweets:
            print("No tweets found in database")
            return
            
        print(f"\nFound {len(tweets)} tweets:")
        print("-" * 80)
        for tweet in tweets:
            tweet_id, content, author, summary = tweet
            print(f"Tweet ID: {tweet_id}")
            print(f"Author: {author}")
            print(f"Content: {content[:100]}...")
            print(f"Summary: {summary}")
            print("-" * 80)

if __name__ == "__main__":
    print_tweets()
