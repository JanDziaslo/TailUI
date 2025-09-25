# Release Guide

This guide explains how to create releases with DEB packages for the Tailscale GUI application.

## Creating a Release

### Method 1: Using Git Tags (Recommended)

1. Make sure your changes are committed and pushed to the main branch
2. Create and push a version tag:
   ```bash
   git tag v1.0.1
   git push origin v1.0.1
   ```
3. GitHub Actions will automatically:
   - Build the DEB package
   - Create a GitHub Release
   - Upload the DEB package to the release

**Important:** Make sure to create an actual git tag (not a branch). The workflow only creates releases for tags starting with 'v'.

### Method 2: Manual Workflow Trigger

1. Go to the "Actions" tab in your GitHub repository
2. Select "Build DEB Package" workflow
3. Click "Run workflow"
4. Choose the branch and click "Run workflow"
5. The package will be available as an artifact (but **not** as a release)

**Note:** Manual workflow runs do not create GitHub releases. They only build the package and upload it as an artifact for testing purposes.

### Method 3: Creating Release Manually

1. Go to "Releases" in your GitHub repository
2. Click "Create a new release"
3. Create a new tag (e.g., `v1.0.1`) - **this must be a proper git tag**
4. Fill in the release notes
5. Publish the release
6. GitHub Actions will build and attach the DEB package automatically

**Important:** This method creates both the git tag and the release simultaneously.

## Version Management

- Update the `VERSION` file when you want to change the version number
- Use semantic versioning (e.g., `1.0.0`, `1.0.1`, `1.1.0`)
- Update `CHANGELOG.md` with your changes

## Package Information

The DEB package includes:
- Application files in `/usr/share/tailscale-gui/`
- Executable wrapper in `/usr/bin/tailscale-gui`
- Desktop file for system integration
- Icon file in `/usr/share/pixmaps/`
- License and documentation in `/usr/share/doc/tailscale-gui/`

## Installation for End Users

Users can install the package with:
```bash
# Download from releases
wget https://github.com/JanDziaslo/tailscale-GUI/releases/latest/download/tailscale-gui_*.deb

# Install
sudo dpkg -i tailscale-gui_*.deb

# Fix dependencies if needed
sudo apt-get install -f

# Run
tailscale-gui
```

## Troubleshooting

If the GitHub Action fails:
1. Check the Actions tab for error logs
2. Ensure all required files are present (main.py, gui.py, etc.)
3. Verify the VERSION file contains a valid version number
4. Make sure the workflow file syntax is correct
5. **For release creation failures:**
   - Ensure you're creating a **git tag** starting with 'v' (e.g., v1.0.1), not a branch
   - Check that you have proper permissions to create releases
   - The workflow only creates releases for tag pushes or release events, not manual runs