# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] - 2024-09-25

### Added
- Initial release of Tailscale GUI
- Basic Tailscale connection management (up/down)
- Exit node selection and management
- Device list with online status and IP addresses
- Public IP information display with geolocation
- Dark theme UI
- Automatic refresh every 5 seconds
- Asynchronous IP fetching to prevent UI blocking
- DEB package build system via GitHub Actions
- Desktop file integration for Linux systems

### Features
- PySide6-based GUI interface
- Support for Python 3.10+
- Tailscale CLI integration
- Real-time status monitoring
- System tray integration ready (future enhancement)

### Package
- Automated DEB package creation
- System package manager integration
- Proper dependency management
- Desktop environment integration