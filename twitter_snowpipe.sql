
/* creating warehouse and database */
use role sysadmin

create or replace warehouse twitter_wh
    with warehouse_size ='x-small'
    auto_suspend = 300
    auto_resume = true
    initially_suspended = true;

create or replace database twitter_db;
use schema twitter_db.public;

/* create External S3 stage pointing to S3 bucket storing the tweets */
CREATE or replace STAGE twitter_db.public.tweets
    URL = 's3://my-twitter-bucket/'
    CREDENTIALS = (AWS_KEY_ID = 'your_aws_key_id'
    AWS_SECRET_KEY = 'your_aws_secret_key')
    file_format=(type='JSON')
    COMMENT = 'Tweets stored in S3';

/*Create new table for storing JSON data in native format into a VARIANT column*/

create or replace table tweets(tweet variant);

/* create a pipe to load data automatically from the  S3 stage into the "tweets" snowflake table */
create or replace pipe twitter_db.public.tweetpipe auto_ingest=true as
    copy into twitter_db.public.tweets
    from @twitter_db.public.tweets
    file_format=(type='JSON');

/* check the pipe */
show pipes;



   