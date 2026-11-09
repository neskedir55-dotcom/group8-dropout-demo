# Sub-module 6.4: Cloud Deployment (Group 8)

**Service:** Student Dropout Early-Warning API (FastAPI in Docker)
**Status of this document:** the service is deployed on Render and publicly reachable (see section 4). The cold and warm response times are measured (section 5) and the rollback owners are named (section 6). Nothing is left to fill in.

## 1. Platform comparison

| | **Render (chosen)** | **Hugging Face Spaces** |
|---|---|---|
| Cost | Free web service tier | Free for public apps |
| Effort | Low: connects to GitHub, builds our existing Dockerfile, simple dashboard | Low to medium: also runs Docker, but needs its own app settings (port and Space configuration) |
| Limits | Free services sleep after a period of inactivity, so the first request is slow (cold start); limited memory; files written at runtime are erased on restart | Free hardware is limited; designed more for model demos than for an API service |
| Fit for this project | Very good: our API is a small Docker service that needs a public `/health` and `/predict` | Good for demos, but less natural for a plain API |

**Choice: Render.** It builds our existing `Dockerfile` directly from GitHub with no extra configuration, gives a public URL, and the free tier is enough for our small model (the model file is about 16 KB). Its main cost is the cold start, which we measure and plan for in section 5. Free-tier terms change often, so the current pricing and limits must be checked on each provider's site before deploying.

## 2. Configuration (nothing secret is in the code)

Settings are read from environment variables in `app/config.py`. Every setting has a default, so the API still runs locally with no variables.

| Variable | Set on the platform | Default | Purpose |
|---|---|---|---|
| `MODEL_PATH` | `model_artifacts/dropout_risk_model.joblib` | same | Which saved pipeline to load |
| `THRESHOLD` | `0.38` | value in `model_metadata.json` (0.38) | Dropout decision threshold |
| `MODEL_VERSION` | `1.0.0` | `1.0.0` | Label written to every response and every log row (6.6) |
| `LOG_DB_PATH` | not needed | `logs/predictions.db` | Where the prediction log is written (6.6). On free tiers this file is erased on restart. |
| `PORT` | set automatically by the platform | `8000` | Port the API listens on (the Dockerfile reads it) |

This API has **no password, key or token**, so there are no secrets to hide, and no `API_KEY` is used. The repository still follows the secret-safe rules: `.gitignore` excludes `.env` files, `.env.example` lists only the setting names with non-secret values, and `.dockerignore` keeps `.env` files out of the image.

**Evidence files:** [.gitignore](.gitignore), [.env.example](.env.example), this variable list. (Never submit real secret values; there are none here.)

## 3. Deployment steps (for the person deploying)

You need a free GitHub account and a free Render account. Docker is not needed on your computer, because Render builds the image.

1. **Prepare the repository folder.** Use the contents of the `prediction_api/` folder as the repository root, so the `Dockerfile` sits at the top level. Do not include any `.zip` file.
2. **Upload to GitHub.** Create an empty repository (no README), then upload the files with the website (Add file, then Upload files), or push with Git or GitHub Desktop. Upload dotfiles too: `.gitignore`, `.dockerignore` and `.env.example`. Check on GitHub that **no `.env` file** is there and that `.env.example` is. Create a tag `v1.0` for this first release.
3. **Create the web service on Render.** New, then Web Service, connect GitHub, select the repository and branch `main`. Runtime: **Docker**. Instance type: **Free**.
4. **Add environment variables:** `MODEL_PATH` = `model_artifacts/dropout_risk_model.joblib` and `THRESHOLD` = `0.38`. Do not set `PORT`; Render provides it.
5. **Set the Health Check Path to `/health`** (advanced settings), then create the service and watch the build log until it is live.
6. **Verify** (section 4) and measure the cold start (section 5).

## 4. Verification from the public URL

Public URL: **https://group-8-student-dropout-risk-api.onrender.com** (interactive documentation: https://group-8-student-dropout-risk-api.onrender.com/docs)

```bash
curl https://<your-service>.onrender.com/health
curl -s -X POST https://<your-service>.onrender.com/predict \
  -H "Content-Type: application/json" \
  -d @examples/valid_student.json
```

Expected: `/health` returns `{"status":"healthy","model_version":"1.0.0"}`, and `/predict` returns Dropout probability **0.4128**, `high_risk`, which is the same as the local and Docker runs. The first call may take about a minute. Evidence: [evidence/cloud_render_docs_health_predict.png](evidence/cloud_render_docs_health_predict.png) is a screenshot of the deployed service's `/docs` page on Render. It shows the public address in the browser bar, `GET /health` executed, and `POST /predict` returning HTTP 200 with a valid prediction (Dropout 0.0002, `low_risk`, predicted outcome Graduate, threshold 0.38, model version 1.0.0). It was run with the default example in the API documentation, so its numbers differ from the 0.4128 result of `examples/valid_student.json`.

## 5. Cold-start note

| Measurement | Time |
|---|---|
| First call after the service was idle (cold) | **31.6 seconds** |
| Second call right after (warm) | **0.25 seconds** |

Both times were measured on Nov 8, 2026 with `curl -s -o /dev/null -w "%{time_total} seconds\n" https://group-8-student-dropout-risk-api.onrender.com/health`, run twice in a row from a laptop. Screenshot: [evidence/cloud_cold_warm_timing.png](evidence/cloud_cold_warm_timing.png). The warm call was about 120 times faster than the cold one.

On the free tier the service sleeps after a period of inactivity (currently about 15 minutes; check the current documentation). **Plan for the demonstration:** a few minutes before the demo starts, open the `/health` address to wake the service, then keep it open in a tab. Tell the audience that the very first request can be slow. We will not discover this behavior in front of the reviewers.

## 6. Rollback plan

- **What is the last known good version?** Git tag `v1.0` (the first deployed commit). Each later release gets a new tag (`v1.1`, `v1.2`, and so on).
- **How is it redeployed?** In the Render dashboard, open the service's deploy history and redeploy the previous working deploy. If that option is missing, undo the faulty change in Git with `git revert <commit-id>` and push to `main`. Render then redeploys automatically.
- **Who is allowed to do it?** The group coordinator, Nesredin Kedir, and the person who deployed the service, Temesgen, because they have access to the repository and the Render account.
- **How are users told?** Post a message in the group chat and tell the reviewers that the service is temporarily unavailable or has returned to the earlier version. Check `/health` and one `/predict` call after the rollback to confirm it works.

## 7. Review questions

1. **Why must a secret never be in a Dockerfile or source code, even in a private repository?** It becomes part of the image layers and the Git history, which are copied around, shared and sometimes made public by mistake. Anyone who gets the code gets the secret.
2. **What is a cold start and how do we handle it?** The delay when a sleeping free service wakes up for the first request, up to about a minute. We call `/health` a few minutes before the demo and warn the audience.
3. **Works locally but fails after deployment: first three places to look?** (1) The platform's build and runtime logs. (2) The environment variables and the port (`PORT`, `--host 0.0.0.0`). (3) The health check path and whether all files (model, `app/`) were committed to GitHub.
4. **Why prepare a rollback plan before a release?** During a failure there is stress and no time to think; we need to already know the last good version, how to restore it and who may do it.
5. **Why does `CMD` read `PORT`?** The platform chooses the port and passes it in `PORT`. A service listening on a fixed port looks unresponsive to the platform.
6. **A key was committed and deleted in a later commit. Is it safe?** No. It stays in the Git history. It must be revoked, a new key created, and the history cleaned if needed.
