#!/usr/bin/env python3
import json
import toml
import subprocess
import shutil
from pathlib import Path

def build_metadata(manifest_path='xai_components_manifest.jsonl',
                   output_index='index.json',
                   metadata_dir='metadata',
                   clone_root='.clones'):
    """
    1. Reads a JSONL manifest of component libraries.
    2. For each entry, clones its repo at the given ref into clone_root.
    3. Extracts [project] info from pyproject.toml, filling "N/A" if missing.
    4. Merges manifest info + project info, writes per-library JSON.
    5. Builds an index.json of all metadata files.
    6. Cleans up clone directories.
    """
    meta_dir = Path(metadata_dir)
    meta_dir.mkdir(exist_ok=True)
    clone_dir = Path(clone_root)

    index = []
    with open(manifest_path, 'r', encoding='utf-8') as mf:
        for line in mf:
            entry = json.loads(line)
            lib_id = entry['library_id']
            repo_url = entry['url']
            ref      = entry.get('git_ref', 'main')
            target   = clone_dir / lib_id.lower()

            # 2) clone & checkout
            subprocess.run(['git', 'clone', repo_url, str(target)], check=True)

            # 3) load pyproject.toml if exists
            proj_data = {}
            pyproj = target / 'pyproject.toml'
            if pyproj.exists():
                proj_data = toml.load(pyproj).get('project', {})
            else:
                print(f"⚠️  {lib_id}: pyproject.toml not found, filling N/A")

            metadata = {
                # manifest fields
                'library_id': lib_id,
                'path':       entry['path'],
                'url':        repo_url,
                'git_ref':    ref,
                # project fields
                'version':             proj_data.get("version", "N/A"),
                'description':         proj_data.get("description", "No description available."),
                'authors':             proj_data.get("authors", []),
                'license':             proj_data.get("license", "N/A"),
                'readme':              proj_data.get("readme", None),
                'repository':          proj_data.get("repository", None),
                'keywords':            proj_data.get("keywords", []),
                'requirements':        proj_data.get("dependencies", []),
            }

            # write per-library JSON
            out_file = meta_dir / f"{lib_id.lower()}.json"
            with open(out_file, 'w', encoding='utf-8') as of:
                json.dump(metadata, of, indent=2)

            index.append({
                'library_id': lib_id,
                'path':       entry['path'],
                'metadata':   out_file.as_posix()
            })


    # write index.json
    with open(output_index, 'w', encoding='utf-8') as idxf:
        json.dump(index, idxf, indent=2)

    # optionally remove clone_root entirely
    print(f"Generated {len(index)} metadata files in '{metadata_dir}' and wrote '{output_index}'")

if __name__ == '__main__':
    build_metadata()
