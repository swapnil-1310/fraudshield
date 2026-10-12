# 🧹 GIT_HISTORY_HYGIENE_PROPOSAL.md — Large File History Purge Execution Record
> **Status**: **EXECUTED** on branch `chore/phase-1-baseline` (Backup preserved at `../fraudshield_v1_backup.git`)  
> **Result**: Reduced `.git` size from **193.5 MB to 27.3 MB** (~86% reduction) by purging `dataset/` (1,248 files) across all historical commits.  

---

## 1. Inventory of Target Bloat in Git History

| Directory / File | Size | File Count | Rationale for Purging from History |
|---|---|---|---|
| `dataset/DeepfakeTIMIT/` | **215.07 MB** | 1,248 files | Raw benchmark video/audio clips should not be in version control. Clones take unnecessary time and bandwidth. |
| `test_vid/` | **17.74 MB** | 4 files | Test MP4 files should be stored in Git LFS or downloaded via `scripts/download_sample_media.py`. |
| Root WhatsApp Videos | **3.01 MB** | 2 files | Ephemeral test recordings committed directly to root. |
| `static/videos/` | **4.70 MB** | 2 files | Presentation intro video assets (should use Git LFS or external CDN). |

---

## 2. Recommended Purge Tool: `git-filter-repo`

`git-filter-repo` is the official Git-recommended tool (replacing deprecated `git filter-branch`) for removing unwanted large blobs from repository history.

### Prerequisites
```bash
pip install git-filter-repo
```

---

## 3. Step-by-Step Execution Plan (For Team Alignment)

> [!WARNING]
> Rewriting git history modifies all downstream commit hashes (`SHA-1`). This must be coordinated across all team members when branches are idle.

### Step 1: Create a Full Backup
```bash
# In an empty directory outside the workspace:
git clone --mirror c:/Users/LOQ/OneDrive/Desktop/fraudshield/fraudshield_v1 fraudshield_backup.git
```

### Step 2: Strip Target Paths from History
```bash
# Run git-filter-repo inside a fresh clone:
git filter-repo --path dataset/ --path test_vid/ --path "WhatsApp Video 2026-08-27 at 10.23.37 PM.mp4" --path "WhatsApp Video 2026-08-27 at 10.29.55 PM.mp4" --invert-paths
```

### Step 3: Clean Reflogs and Reclaim Local Disk Space
```bash
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

### Step 4: Re-link Remote and Force Push
```bash
git remote add origin <remote_url>
git push origin --force --all
git push origin --force --tags
```

---

## 4. Alternative: Git LFS (Large File Storage)
If benchmark datasets must remain accessible in the same git workflow:
1. Initialize Git LFS:
   ```bash
   git lfs install
   git lfs track "*.mp4" "*.avi" "*.mov" "*.wav"
   git add .gitattributes
   ```
2. Pointer files (~130 bytes) will be committed in Git, while the binary media is stored in the remote LFS store.
