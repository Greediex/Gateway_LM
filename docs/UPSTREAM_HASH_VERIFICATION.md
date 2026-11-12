# Pinned upstream hash verification (CI repair)

GitHub Actions for branch `refactor/gateway-lm-composite-adapter-pr01`
exposed a pre-existing mismatch between the source-file SHA-256 values in
Gateway LM and the files obtained by cloning the exact upstream commit IDs
in `setup_upstream.py`.

The upstream commit IDs are **unchanged**:

- GoS: `203f60a2c689da055ce1ac351eb3cb9912a3bca7`
- SkillDAG: `2bd7baffae58854018f75857e5626a4a28a705ae`

GitHub Actions runner computed the following hashes with `sha256sum`
after cloning and checking out those commit IDs:

| Source file | SHA-256 at pinned commit |
| --- | --- |
| `graph-of-skills/gos/core/retrieval.py` | `32bd2464164374079448531ef377bea65cdcccd32ed8242067fa83023e07ee5a` |
| `SkillDAG/src/skilldag/search.py` | `5bed3919f5a9676e40ea7ba1d3bf8c06324f867161e0c0e2fb44da9f455795ff` |
| `SkillDAG/src/skilldag/graph.py` | `97a181273002647a97d58628af588b5843e73d9873e6e5b7768eb7315051456b` |

The stored hash constants were updated to **these exact values**.
The check remains fail-closed: altered source will still be rejected.
This does not bypass source verification or silently patch upstream files.

Reference CI log: https://github.com/Greediex/Gateway_LM/actions/runs/43155102669

Once source verification passes, regression tests are still required.
