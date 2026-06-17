# osm-tags-to-object

## Data Storage

All data for this project lives on the Hugging Face bucket:

```
hf://buckets/NoeFlandre/osm-tags-to-object
```

**Do not store data locally.** Anything that would otherwise live in `./data/` (or anywhere else on disk) must be synced to and from the bucket using the `hf` CLI.

### Pulling data from the bucket

```bash
hf sync hf://buckets/NoeFlandre/osm-tags-to-object ./data
```

### Pushing local changes to the bucket

```bash
hf sync ./data hf://buckets/NoeFlandre/osm-tags-to-object
```

### Typical workflow

1. Pull the latest data: `hf sync hf://buckets/NoeFlandre/osm-tags-to-object ./data`
2. Work with files under `./data/`
3. Push your changes back: `hf sync ./data hf://buckets/NoeFlandre/osm-tags-to-object`

The `./data/` directory is gitignored, so it stays in sync with the bucket rather than the repository.
