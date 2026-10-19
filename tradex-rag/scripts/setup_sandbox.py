"""Create local OpenSandbox settings without printing credentials."""
from pathlib import Path
import subprocess
import uuid

root = Path(__file__).resolve().parents[1]
config = root / 'var' / 'sandbox.toml'
config.parent.mkdir(exist_ok=True)
if not config.exists():
    subprocess.run([str(root / '.venv/bin/opensandbox-server'), 'init-config', str(config), '--example', 'docker'], check=True)
env_path = root / '.env'
env = env_path.read_text() if env_path.exists() else ''
values = dict(line.split('=', 1) for line in env.splitlines() if '=' in line and not line.startswith('#'))
key = values.get('SANDBOX_API_KEY') or uuid.uuid4().hex
settings = {'SANDBOX_API_KEY': key, 'SANDBOX_DOMAIN': '127.0.0.1:8080', 'TRADEX_SANDBOX_ENABLED': '1', 'TRADEX_WEB_ENABLED': '1'}
lines = env.splitlines()
for name, value in settings.items():
    lines = [line for line in lines if not line.startswith(name + '=')]
    lines.append(name + '=' + value)
env_path.write_text('\n'.join(lines) + '\n')
env_path.chmod(0o600)
text = config.read_text().replace('# api_key = "your-secret-api-key"', 'api_key = "' + key + '"')
text = text.replace('resolve_internal = true', 'resolve_internal = false')
text = text.replace('path = "~/.opensandbox/opensandbox.db"', 'path = "' + str(root / 'var/opensandbox.db') + '"')
text = text.replace('# publish_host = "127.0.0.1"', 'publish_host = "127.0.0.1"')
text = text.replace('mode = "dns"', 'mode = "dns+nft"')
config.write_text(text)
config.chmod(0o600)
print('Local sandbox configuration saved. Credentials remain in .env and var/sandbox.toml.')
