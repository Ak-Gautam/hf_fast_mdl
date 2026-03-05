# hf_fast_mdl

Small CLI wrapper around `huggingface_hub`.

This project is not trying to replace the official tooling. It is mainly for personal convenience and AI-agent workflows where I want a short command with:
- interactive file picker mode
- non-interactive pattern mode
- simple local cache/offline flags

## Install (macOS)

```bash
cd /Users/gautam/projects/personal/hf_fast_mdl
bash install-cli-mac.sh
```

Then run from anywhere:

```bash
hfmdl --help
```

## Usage

Interactive picker:

```bash
hfmdl unsloth/Qwen3.5-9B-GGUF
```

Non-interactive download:

```bash
hfmdl gpt2 -p "*.json" --yes -o ~/Downloads/gpt2_files
```

Offline/cache examples:

```bash
hfmdl gpt2 -p "README.md" --yes --cache-dir ~/.cache/hf_fast_mdl
hfmdl gpt2 -p "README.md" --yes --offline
```

## Notes

- Main command: `hfmdl`
- Alias: `hf_fast_mdl`
