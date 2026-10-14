# DeepSeek native builds implementation plan

> Execute inline using superpowers:executing-plans.

**Goal:** Remove emulated ARM64 compilation and excessive cache export from DeepSeek's GitHub build.

**Design:** Use Docker's pinned reusable GitHub Builder for native AMD64/ARM64 builds and manifest assembly. Preserve version, latest, and 12-character SHA tags through the existing resolver; keep dry runs non-publishing. Use per-image caches and final-image-only caches for DeepSeek. Remove workflow-only image rebuild triggers. Shallow-fetch the pinned upstream revision and omit safe development-only files; retain dependency and runtime resource layouts.

## Tasks

- [x] Replace DeepSeek's generic matrix row with tag preparation, reusable native builds, and Docker Hub description jobs.
- [x] Scope generic/ComfyUI-GGUF caches independently and remove workflow-file entries from image filters.
- [x] Shallow-fetch upstream; prune Git history, snapshots, docs, website, and benchmarks after compilation.
- [x] Add a build-time smoke checking non-root execution, browser plugin imports, authenticated HTML, and shutdown using an isolated temporary DSH_HOME.
- [x] Validate tag tests, workflow with actionlint, Compose, shell/Node syntax, and native ARM64 image startup.
- [ ] Review the final diff, push, and verify GitHub uses native platform runners and publishes both architectures.

## Evidence and rulings

- Existing build: AMD64 install/build 243.3s; ARM64 install/build 2879.3s; cache export 688.1s.
- Docker reusable workflow pinned at 58cb9f5b71b1836d6f690c1e95effdeb9b98cb8a; verified cache scopes append platform suffix.
- Startup validation belongs inside the Docker build because the reusable workflow has no custom test hook. Temporary home is removed after validation.
- Runtime dependencies remain intact: pruning the full pnpm dependency graph needs a separate runtime-closure investigation.

- Local validation: 6 tag-resolver tests pass; Compose and actionlint pass; pruned ARM64 runtime passed startup smoke in 1.8s. GitHub source build remains the end-to-end verification.
