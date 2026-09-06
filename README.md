# Questionnaire responses

Private storage for questionnaire responses. **Keep this repository private** —
every file in `responses/` contains an email address.

## What is in here

| File or folder | What it is |
| --- | --- |
| `responses/` | One JSON file per person, written automatically when they submit |
| `responses.csv` | All responses in one table, rebuilt automatically. This is the file to download |
| `SCORING-KEY.csv` | Which answer column belongs to which scale, and its direction |
| `collate.py` | Builds `responses.csv` from the individual files |
| `.github/workflows/collate.yml` | Runs `collate.py` whenever a response arrives |
| `.github/workflows/watchdog.yml` | Checks daily that collection still works, opens an issue if not |

## How responses get here

The questionnaire lives at a Cloudflare Worker, not in this repository. When
someone submits, the Worker writes a file into `responses/` using a GitHub
token stored in the Worker's settings.

- Questionnaire link: `https://REPLACE-ME.workers.dev/`
- Health check: `https://REPLACE-ME.workers.dev/healthz`
- Cloudflare dashboard: dash.cloudflare.com → Workers & Pages

Fill in those addresses once you have them.

## Getting the data

Click `responses.csv`, then the download icon. One row per person. Columns
`a1`–`a50` and `b1`–`b48` hold raw 1–5 answers, alongside email, submission
time, and how long they took.

To score: sum the items belonging to each scale, taking `+` items as the answer
given and `-` items as `6 − answer`. `SCORING-KEY.csv` lists which is which.

## If responses stop arriving

Open the health check link above. It says what is wrong in plain words —
usually the token expired, was revoked, or lost its Contents write permission.
Generate a new fine-grained token on GitHub with **Contents: Read and write**
on this repository, then update the `GH_TOKEN` secret on the Worker.

## Notes

- Respondents see no score and no result, only a thank-you screen.
- The same person can submit twice. Deduplicate on email when analysing.
- Delete this repository when the project is finished. The emails have no
  reason to outlive it.
