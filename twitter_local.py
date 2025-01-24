import json
import os
import queue
import threading
import time
from datetime import datetime
import tweepy
import boto3
import logging
from dotenv import load_dotenv

# load environment variables
load_dotenv()

# set up logging
logging.basicConfig(level = logging.INFO, format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# set up AWS and Twitter Credentials
BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
if not BEARER_TOKEN:
    raise ValueError("No Twitter Bearer Token provided")

BUCKET = os.getenv("AWS_S3_BUCKET")
if not BUCKET:
    raise ValueError("No AWS S3 Bucket provided")

KEYWORD = os.getenv("TWITTER_KEYWORD")
if not KEYWORD:
    raise ValueError("No Twitter Keyword provided")

# queue and event threading
pipeline = queue.Queue()
event = threading.Event()

# Consumer function
def consumer():
    # consume tweets from the pipeline ie. queue and upload to S3

    tweet_list = [] # To store tweets in a batch
    total_count = 0 # To keep track of total tweets
    s3 = boto3.client('s3') # S3 client

    #Process tweets from the pipeline ie. queue
    while not event.is_set() or not pipeline.empty(): # Loop until the event is set and the pipeline is empty
        try:
            # step 1 : get the tweet from the pipeline
            data = pipeline.get()

            # step 2 : prase the tweet into json and adding metadata
            data_dict = json.loads(data)
            data_dict.update({
                "keyword": KEYWORD
            })

            # step 3 : append the tweet to the tweet_list
            tweet_list.append(json.dumps(data_dict))
            total_count += 1

            # step 4 : logging the tweet for monitoring
            if total_count % 2 == 0:
                logging.info(f"Processed {total_count} tweets")

            # step 5 : if the tweet_list reaches 10, upload to S3
            if total_count % 10 == 0:
                filename = f"tweets_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
                logging.info(f"Uploading {len(tweet_list)} records as {filename} to S3")

                # saving files locally
                with open(filename, 'w') as tweet_file:
                    tweet_file.writelines(tweet_list)

                # Generate S3 key (path in the bucket) based on date and time
                now = datetime.now()
                key = f"{KEYWORD}/{now.year}/{now.month}/{now.day}/{now.hour}/{now.minute}/{filename}"
                logging.info(f"Uploading {filename} to S3 bucket: {BUCKET}, key: {key}")

                # Upload the file to S3
                s3.upload_file(filename, BUCKET, key)
                logging.info(f"Successfully uploaded {filename} to S3")

                # Reset tweet list for the next batch and delete the local file
                tweet_list = []
                os.remove(filename)

        except Exception as e:
            # Log any errors encountered during processing
            logging.error(f"Error in consumer: {e}")

class TweetStream(tweepy.StreamingClient):
    """StreamListener for handling tweets."""

    def on_data(self, raw_data):
        """Called when raw data (tweet) is received."""
        try:
            pipeline.put(raw_data)
            return True
        except Exception as e:
            logging.error(f"Error in on_data: {e}")
            return False

    def on_error(self, status_code):
        """Called when an error occurs."""
        logging.error(f"Stream error: {status_code}")
        if status_code in (420, 429):  # Rate limit errors
            return False  # Disconnect the stream


if __name__ == "__main__":
    try:
        # Initialize the streaming client
        stream = TweetStream(bearer_token=BEARER_TOKEN)

        # Add a rule to filter tweets containing the keyword
        logging.info(f"Setting up stream with keyword: {KEYWORD}")
        stream.add_rules(tweepy.StreamRule(value=KEYWORD))

        # Start the consumer thread
        stream_thread = threading.Thread(target=consumer)

        # Start the Twitter stream
        logging.info("Starting the Twitter stream...")
        stream.filter(threaded=True)  # Stream in a separate thread
        stream_thread.start()

        # Let the script run for 15 minutes
        time.sleep(900)
        event.set()

    except Exception as e:
        logging.error(f"Error in main: {e}")
                    
                   