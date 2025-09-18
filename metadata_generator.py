#!/usr/bin/env python3
import json
import toml
import subprocess
from pathlib import Path

CORE_ORIGIN = "core"

def _git_clone_once(repo_url: str, target: Path, ref: str):
    if target.exists() and (target / ".git").exists():
        print(f"✓ Using cached clone: {target}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["git", "clone", "--depth", "1"]
    if ref:
        cmd += ["--branch", ref]
    cmd += [repo_url, str(target)]
    subprocess.run(cmd, check=True)

def build_metadata(manifest_path='xai_components_manifest.jsonl',
                   output_index='index.json',
                   metadata_dir='metadata',
                   clone_root='.clones'):
    """
    1. Reads a JSONL manifest of component libraries.
    2. For each entry, clones its repo at the given ref into clone_root.
    3. Extracts [project] info from pyproject.toml, using null if missing (lists default to []).
    4. Merges manifest info + project info, writes per-library JSON.
    5. Builds an index.json of all metadata files.
    6. Cleans up clone directories.
    """
    meta_dir = Path(metadata_dir)
    meta_dir.mkdir(exist_ok=True)
    clone_dir = Path(clone_root)
    clone_dir.mkdir(exist_ok=True)
    core_clone_cache = {}  

    index = []
    with open(manifest_path, 'r', encoding='utf-8') as mf:
        for line in mf:
            entry = json.loads(line)
            lib_id = entry['library_id']
            repo_url = entry['url']
            ref      = entry.get('git_ref', 'main')
            origin   = entry.get('origin') 

            if origin == CORE_ORIGIN:
                key = (repo_url, ref)
                if key not in core_clone_cache:
                    repo_name = Path(repo_url.rstrip('/')).stem  
                    shared = clone_dir / f"{repo_name}-{ref}".lower()
                    _git_clone_once(repo_url, shared, ref)
                    core_clone_cache[key] = shared
                target = core_clone_cache[key]
            else:
                target = clone_dir / lib_id.lower()
                _git_clone_once(repo_url, target, ref)

            proj_data = {}
            xircuits_cfg = {}

            if origin == CORE_ORIGIN:
                lib_path = entry.get('path')
                if not lib_path:
                    raise RuntimeError(f"[{lib_id}] core entry is missing 'path' in manifest.")
                lib_root = target / lib_path
                if not lib_root.exists():
                    raise RuntimeError(f"[{lib_id}] core lib path not found: {lib_root}")

                pyproj = lib_root / 'pyproject.toml'
                if not pyproj.exists():
                    raise RuntimeError(f"[{lib_id}] core pyproject.toml is required at: {pyproj}")

                cfg = toml.load(pyproj)
                proj_data    = cfg.get('project', {})
                xircuits_cfg = (cfg.get('tool') or {}).get('xircuits', {})

                default_example_path = entry.get("default_example_path") or xircuits_cfg.get("default_example_path")
                if not default_example_path:
                    raise RuntimeError(f"[{lib_id}] core default_example_path is required (manifest or [tool.xircuits]).")

            else:
                pyproj = target / 'pyproject.toml'
                if pyproj.exists():
                    cfg = toml.load(pyproj)
                    proj_data    = (cfg.get('project') or {})
                    xircuits_cfg = ((cfg.get('tool') or {}).get('xircuits') or {})
                else:
                    print(f"⚠️  {lib_id}: pyproject.toml not found at repo root; using nulls.")

                default_example_path = entry.get("default_example_path", xircuits_cfg.get("default_example_path"))

            metadata = {
                # manifest fields
                'library_id': lib_id,
                'path':       entry['path'],
                'url':        repo_url,
                'git_ref':    ref,
                'origin':     origin,
                # project fields
                'version':      proj_data.get("version"),
                'description':  proj_data.get("description"),
                'authors':      proj_data.get("authors", []),
                'license':      proj_data.get("license"),
                'readme':       proj_data.get("readme", None),
                'repository':   proj_data.get("repository", None),
                'keywords':     proj_data.get("keywords", []),
                'requirements': proj_data.get("dependencies", []),
                'default_example_path': default_example_path,
            }

            # write per-library JSON
            out_file = meta_dir / f"{lib_id.lower()}.json"
            with open(out_file, 'w', encoding='utf-8') as of:
                json.dump(metadata, of, indent=2)

            index.append({
                "library_id":           lib_id,
                "name":                 entry.get("name", proj_data.get("name")),
                "path":                 entry.get("path"),
                "metadata":             out_file.as_posix(),
                "version":              entry.get("version", metadata.get("version")),
                "description":          entry.get("description", metadata.get("description")),
                "authors":              entry.get("authors", metadata.get("authors")),
                "license":              entry.get("license", metadata.get("license")),
                "readme":               entry.get("readme", metadata.get("readme")),
                "repository":           entry.get("repository", metadata.get("repository")),
                "keywords":             entry.get("keywords", metadata.get("keywords")),
                "requirements":         entry.get("requirements", metadata.get("requirements")),
                "url":                  entry.get("url", metadata.get("url")),
                "git_ref":              entry.get("git_ref", metadata.get("git_ref")),
                "origin":               origin,
                "default_example_path": default_example_path,
            })


    # write index.json
    with open(output_index, 'w', encoding='utf-8') as idxf:
        json.dump(index, idxf, indent=2)

    # optionally remove clone_root entirely
    print(f"Generated {len(index)} metadata files in '{metadata_dir}' and wrote '{output_index}'")

if __name__ == '__main__':
    build_metadata()
