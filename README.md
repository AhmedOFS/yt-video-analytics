

##  Setup Instructions

- Create a `.env` file and add the var API_KEY with the YouTube Data API v3 key. 

- Install dependencies from the `environment.yml` file

- Run the `data_pipeline.ipynb` notebook. The notebook leverages all defined classes to perform the API fetches, data transformation, SQLite DB creation and loading the data into it.

 - For the Analysis queries and results, reference  the `analysis.ipynb` notebook. The notebook contains the questions, the queries and the results which can be replicated by re-running the cells. 


When run, the pipeline generates `/Raw` , `/L1` and `/L2` where intermediate data layers are stored. 

The pipeline automatically logs all API failures due to unavailable ids or authorization errors as well as all records dropped in the data cleaning and their reasons. Those can be found in `/logs`.

