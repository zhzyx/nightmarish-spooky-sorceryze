"""Prepare a fresh machine-local, immutable three-role installation generation."""

import argparse
import hashlib
import json
import os
import ssl
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROLES = ROOT / "customizations/components/tianxuan/sinan-workorders"
sys.path.insert(0, str(ROLES))


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def certificate(path):
    return hashlib.sha256(ssl.PEM_cert_to_DER_cert(Path(path).read_text("ascii"))).hexdigest()


def prepare(inputs, output):
    from native_entry_runtime import load_config, runner
    from native_role_service import tree_sha256

    def write(name, value):
        path = output / name
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
        return str(path)

    def require(condition, message):
        if not condition:
            raise ValueError(message)

    roles = inputs["roles"]
    require(set(roles) == {"planner", "producer", "reviewer"}, "Three roles required")
    require(len({s["identity"] for s in roles.values()}) == 3, "Independent role identities required")
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    manifest = dict(inputs["installation"])
    require(manifest["version"] == 2 and manifest["mode"] == "production", "Production v2 required")
    commands = manifest["commands"]
    require(set(commands) == {"dispatcher", "checker"}, "Supply checker and dispatcher commands")
    files = manifest["files"]
    for path, expected in files.items():
        require(digest(path) == expected, "Base installation fingerprint changed")
    paths = {ROOT / "tools/ainative/owned_process.py", *ROLES.glob("native_*.mjs")}
    for directory in (ROLES, ROLES.parent / "server", ROLES.parent / "duobao"):
        paths.update(directory.glob("native_*.py"))
    services = {}
    client_peers = set()
    server_peers = set()
    tree = tree_sha256()
    for role, item in roles.items():
        item = dict(item)
        if "broker_inputs" in item:
            require("broker_file" not in item and "broker_sha256" not in item, "Choose one broker source")
            config = dict(item["broker_inputs"])
            template = runner.read(config["template"])
            installed = template["profiles"][0].get("native_installation", config)
            for key in ("node", "python"):
                config[key] = installed[key]
                config[key + "_sha256"] = digest(config[key])
            config.update(
                template_sha256=digest(config["template"]),
                runtime_sha256=runner.runtime_digest(),
                framework_sha256=digest(Path(config["framework"]) / "framework-manifest.json"),
            )
            item["broker_file"] = write(role + "-broker.json", config)
            item["broker_sha256"] = digest(item["broker_file"])
        broker, template = load_config(item["broker_file"], item["broker_sha256"])
        runner.validate_plan(template)
        for profile in template["profiles"]:
            ev = profile["evaluation"]
            require(digest(ev["evidence_ref"]) == ev["evidence_sha256"], "Evaluation evidence changed")
            require(template["task"]["steps"][0]["kind"] in ev["passed_task_types"], "Role evaluation required")
            paths.add(Path(ev["evidence_ref"]))
        shared = {k: item[k] for k in ("address", "port", "ca_file", "broker_file", "broker_sha256")}
        shared["role"] = role
        if role == "producer":
            for field in ("worker_root", "registry"):
                require(Path(item[field]).is_absolute(), "Absolute producer roots required")
                shared[field] = item[field]
        srv, cli = item["server_tls"], item["client_tls"]
        for endpoint in (srv, cli):
            require(set(endpoint) == {"certificate_file", "private_key_file", "certificate_sha256"}, "TLS inputs")
            require(all(Path(endpoint[k]).is_absolute() for k in ("certificate_file", "private_key_file")), "TLS paths")
            require(certificate(endpoint["certificate_file"]) == endpoint["certificate_sha256"], "Certificate changed")
        client_peers.add(cli["certificate_sha256"])
        server_peers.add(srv["certificate_sha256"])
        tls_fields = ("certificate_file", "private_key_file")
        script = ROLES / ("native_entry_producer.py" if role == "producer" else "native_entry_runtime.py")
        server = dict(
            shared,
            **{k: srv[k] for k in tls_fields},
            identity=item["identity"],
            journal=item["journal"],
            tree_sha256=tree,
            peer_sha256=cli["certificate_sha256"],
            script_sha256=digest(script),
        )
        sp = write(role + "-service.json", server)
        client = dict(
            shared,
            **{k: cli[k] for k in tls_fields},
            peer_sha256=srv["certificate_sha256"],
            server_name=item["server_name"],
            tree_sha256=tree,
            service_identity=item["identity"],
            service_sha256=digest(sp),
        )
        cp = write(role + "-client.json", client)
        entry = str(ROLES / "native_role_service.py")
        services[role] = [broker["python"], "-I", "-S", "-B", entry, "serve", "--config", sp, "--sha256", digest(sp)]
        commands[role] = dict(
            argv=[broker["python"], "-B", "-X", "utf8", entry, "call", "--config", cp, "--sha256", digest(cp)],
            env={k: os.environ[k] for k in ("SystemRoot", "WINDIR") if k in os.environ},
        )
        paths.update(Path(p) for p in (cp, broker["python"], broker["node"], broker["template"], item["broker_file"]))
    require(len(server_peers | client_peers) == 6, "Six distinct role certificates required")
    files.update({str(path): digest(path) for path in sorted(paths)})
    write("services.json", services)
    installation = write("installation.json", manifest)
    write("runtime-inputs.json", dict(inputs["runtime_inputs"], version=1, installation=digest(installation)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", type=Path)
    parser.add_argument("new_generation", type=Path)
    args = parser.parse_args()
    prepare(json.loads(args.inputs.read_text("utf-8")), args.new_generation.resolve())
