# From "Script Spaghetti" to `pip install`: A Mini-Guide to Python Packaging 📦🐍

I am thrilled to announce a personal milestone: I have just published my very first Python package to PyPI! 🎉

Meet `umik-base-app`, a modular toolkit designed to make building high-performance audio applications with the **miniDSP UMIK series** measurement microphone effortless.

👉 **Get it now:** `pip install umik-base-app`

But beyond the tool itself, the journey of *packaging* it was a revelation. If you are a developer who has a folder full of "useful scripts" that you are scared to turn into a package, this post is for you.

## 🏗️ The Transformation: Embracing Structure

For a long time, this project was just a folder of loose files. I’d copy-paste `utils.py` from project to project. It was messy, hard to test, and impossible to share.

To fix this, I moved from a "Flat Layout" to the professional **`src` Layout**.

### ❌ Before: Script Spaghetti

Everything is in the root. Imports break if you move files. Hard to distinguish source code from config.

```text
my_project/
├── calibrate.py
├── recorder.py
├── utils.py
├── requirements.txt
└── .gitignore
```

### ✅ After: The `src` Layout

Code lives in a dedicated package directory. Explicit, clean, and ready for distribution.

```text
my_project/
├── pyproject.toml       <-- The configuration brain
├── src/
│   └── umik_base_app/         <-- The actual package
│       ├── __init__.py
│       ├── core/
│       └── apps/
└── tests/
```

## ✨ The "Magic" Config: `pyproject.toml`

The days of `setup.py` are over. The modern standard is `pyproject.toml`.

The coolest part of this configuration is the `[project.scripts]` section. This block is what creates the "magic" terminal commands. When you install my package, pip looks at this list and automatically creates executables in your system path.

Here is the actual snippet from my [pyproject.toml](https://www.google.com/search?q=https://github.com/danielfcollier/py-umik-base-app/blob/main/pyproject.toml):

```toml
[project.scripts]
# Command Name           = "Python Module : Function to Run"
umik-calibrate           = "umik_base_app.apps.umik1_calibrator:main"
umik-list-devices        = "umik_base_app.apps.list_audio_devices:main"
umik-real-time-meter     = "umik_base_app.apps.real_time_meter:main"
umik-recorder            = "umik_base_app.apps.basic_recorder:main"
umik-metrics-analyzer    = "umik_base_app.apps.metrics_analyzer:main"
umik-metrics-plotter        = "umik_base_app.apps.metrics_plotter:main"
```

Because of these few lines, users don't have to type `python src/umik_base_app/apps/real_time_meter.py`. They just type:

```bash
umik-real-time-meter
```

## 🤖 Automating the Release (CI/CD)

The scariest part of packaging is "uploading to PyPI." *What if I upload a broken build?*

I solved this by never uploading manually. I use a **GitHub Actions** workflow that automates the entire process.

In my `.github/workflows/publish.yml`, the process is defined as code:

1. **Trigger:** It only runs when I create a new **Release** in the GitHub UI.
2. **Build:** It uses `uv build` to create the distribution files.
3. **Publish:** It uses `uv publish` to securely upload them to PyPI using trusted authentication (OIDC).

```yaml
# .github/workflows/publish.yml
on:
  release:
    types: [published]

jobs:
  pypi-publish:
    steps:
      - name: Build package
        run: uv build

      - name: Publish to PyPI
        run: uv publish
```

I just click "Draft Release" on GitHub, and the robots handle the rest.

## 🚀 Call to Action

Don't let your useful code rot in a `scripts` folder. Packaging your code forces you to think about structure, dependencies, and usability.

If you want a template to get started, take a look at my configuration. You can copy my `pyproject.toml` and GitHub workflows directly to jumpstart your own library.

👉 **Check out the repo:** [github.com/danielfcollier/py-umik-base-app](https://github.com/danielfcollier/py-umik-base-app)

#Python #OpenSource #PyPI #DevOps #GitHubActions #SoftwareEngineering #Packaging
