


# Solution Design


The pipeline is separated into four different stages: fetching, ingestion, cleaning and loading into an SQLite Database. This stage separation allows for more transparent data operations and easier data quality inspection and error detection allowing for higher pipeline robustness. 
#### Data Stages

1. API fetches: The data is requested from the API and results are saved as raw JSON.
2. Data Ingestion: The data is ingested from the JSON dumps into delta tables in the L1 data layer so that it's ready for the cleaning process.
3. Data Cleaning : The data is loaded from L1 to be checked for duplicates or missing values and for irrelevant columns to be dropped as well as adding the channel names to the videos table. 
4. Loading into DB: the database is initialized if it isn't then the data is loaded from L2.

####  Why SQL?

An SQL databse was selected as the data entities are inherently related. Creating a single NoSQL video collection with comments embedded would make analytics across comments from multiple videos more complex while maintaining two collections would lead to doing aggregations frequently for which relational databases are better optimized. Additionally, indexes on Foreign keys can be used to further optimize relational query execution.


## Scaling Concerns

Some of the bottlenecks identified are: YouTube's api being daily rate limited, the lack of concurrency in the data pipeline operations and memory constraints when loading the delta tables for the data transformations.  

The recommended solutions are as follows: Implement daily scheduled batch fetches while updating data retrieval progress each run. Replace pandas with PySpark for parallel processing and lazy evaluations reducing memory usage and shortening pipeline execution time. 

## Suggested Improvements

More thoroughly check for edge cases and failure modes of API calls that were not encountered and handle them. 