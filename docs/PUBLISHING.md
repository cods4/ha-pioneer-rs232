# Publishing to the HACS default store

This integration already installs as a HACS **custom repository**. To get it
listed in the HACS **default store** (so users can find it without adding the
URL), complete the steps below. Reference:
<https://hacs.xyz/docs/publish/include/>.

## Repository requirements (done in this repo)

- [x] Public GitHub repository
- [x] Repository **description** set
- [x] Repository **topics** set
- [x] **Issues** enabled
- [x] `hacs.json` at the repo root with a `name`
- [x] Integration under `custom_components/pioneer_rs232/`
- [x] `manifest.json` with `domain`, `name`, `documentation`, `issue_tracker`,
      `codeowners`, `version`
- [x] **Validate** workflow running the HACS Action + hassfest
      (`.github/workflows/validate.yml`)

## Remaining steps

1. **Brand assets** — ready-to-submit files are staged at
   `brands/custom_integrations/pioneer_rs232/` (`icon.png` 256×256,
   `icon@2x.png` 512×512; square, trimmed, optimized). To publish, copy that
   `custom_integrations/pioneer_rs232/` folder into a fork of
   [home-assistant/brands](https://github.com/home-assistant/brands) and open a
   PR. Regenerate with `uv run python images/generate_icon.py`. Once the brands
   PR is merged, remove `ignore: brands` from `.github/workflows/validate.yml`.

2. **Green CI** — ensure the Validate workflow passes on `main`.

3. **Create a full GitHub release** (not just a tag), e.g. `v0.3.1`, after the
   actions succeed. HACS shows the latest releases to users.

4. **Submit to `hacs/default`** — fork
   [hacs/default](https://github.com/hacs/default), add
   `cods4/ha-pioneer-rs232` to the `integration` file (alphabetically), and
   open a PR from a branch off `master`, completing the PR template.

After the PR is merged, the repo is picked up in the next scheduled scan.
