There are a list of pre-fetched DBLP in the database. The scripts are used to fetch missing DBLP urls, and upload the results to VIDURA. The results will be appended to the database, and will not affect the existing records.

#### Setup
The script requires Python3 and ssh. The SSH key can be downloaded from the VIDURA web app after authentication. Click on the Account icon in the app bar, then click Get SSH Key.

Install all required python packages
```bash
pip install -r requirements
```

Create a `.env` file under the same directory as `main.py`. The variables include:
- `OUT_DIR`: The directory to find all output files.
- `IN_DIR`: A `.txt` file containing all DBLP urls to crawl.
- `SIMILARITY_THRESHOLD`: The script uses sentence embeddings to obtain the areas of expertise from a DBLP page with all the publication titles. This variable specifies the minimum cosine similarity of the matches.
- `TOPICS`: A `.txt` file with all areas of interest, each in a separate line. This is optional.
- `RESUME`: DBLP website implements rate limiting. When the limit exceeds, the current progress are written to `OUT_DIR/resume.json`. To continue, wait a few minutes, set `RESUME` to the path to `resume.json`, and run the script again. 
- `DB_IP`: The IP address of the database.
- `SSH_USER`: The user name used for SSH connection.
- `SSH_KEY`: The private SSH key file downloaded from VIDURA. 

An example of `.env`:
```bash
OUT_DIR='/tmp/output'
IN_DIR='/tmp/input.csv'
SIMILARITY_THRESHOLD=0.8
DB_IP="ec2-xx-xx-xx-xx.ap-southeast-1.compute.amazonaws.com"
SSH_USER="guest"
SSH_KEY="/private_ssh_key"
```
#### Run
There is a list of existing areas in VIDURA, the new ones (if any) provided in the `TOPICS` input file will be appended to the list. To avoid duplications, run the following command to calculate the similarity between each new expertise and existing ones:
```bash
./similar_pairs.sh
```
The possible duplicates will be written to `OUT_DIR/similar_pairs.csv`. Please review this file and manually edit the input file `TOPICS`. All new topics will be appended to the existing list in the following step.

To prepare all data locally:
```bash
./crawl.sh
```

When the data is ready, upload the results with:
```bash
./upload.sh
```
