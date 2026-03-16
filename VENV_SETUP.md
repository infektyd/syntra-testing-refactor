# Virtual Environment Setup Guide

## Overview

This guide documents the setup and maintenance of the Python virtual environment for SyntraCMT, with special attention to Python 3.13 compatibility and binary extension issues.

## Issue History

### Binary Extension Corruption (October 2026)

**Problem**: The virtual environment contained corrupted pandas compiled extensions (`np_datetime.cpython-313-darwin.so`) causing `mmap` failures and import errors:

```
ImportError: dlopen(...np_datetime.cpython-313-darwin.so, 0x0002):
mmap(size=0x25840) failed with errno=4
```

**Root Cause**: Binary wheels for Python 3.13 were incompatible or corrupted, preventing proper loading of C extensions in numpy/pandas.

**Solution**: Complete virtual environment rebuild with fresh, compatible packages.

## Environment Requirements

### Python Version
- **Required**: Python 3.13.x (tested with 3.13.9)
- **Location**: `/opt/homebrew/bin/python3.13` (Homebrew on macOS)

### Key Package Versions
```
numpy>=2.1.0      # Latest 2.x series, stable with pandas
pandas>=2.2.0     # Official Python 3.13 support
datasets>=4.2.0   # HuggingFace datasets (latest available)
```

## Setup Instructions

### 1. Create Virtual Environment
```bash
/opt/homebrew/bin/python3.13 -m venv .venv
source .venv/bin/activate
python --version  # Should show 3.13.9
```

### 2. Install Dependencies
```bash
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt
```

**Note**: The `--trusted-host` flags work around macOS SSL certificate issues with pip.

### 3. Verify Installation
```bash
python -c "import numpy, pandas, datasets; print('✓ All imports successful')"
```

### 4. Test ARC Benchmark
```bash
python Benchmarks/ARC/bench/datasets_arc.py --subset challenge --split validation --limit 1
```

## Recovery Procedures

### If Binary Extensions Fail
1. **Backup current environment**:
   ```bash
   mv .venv .venv.bak_$(date +%Y%m%d_%H%M%S)
   ```

2. **Create fresh environment** (follow steps 1-3 above)

3. **Test thoroughly** before deleting backup

### If Network Issues Occur
- Use `--trusted-host` flags for pip installs
- Ensure network connectivity for HuggingFace datasets
- ARC loader will use cached data if available

### If Python Version Issues
- Verify Python 3.13.x is installed via Homebrew
- Check that `.venv/bin/python` points to correct version

## Maintenance Notes

### Package Updates
- Pin major versions in `requirements.txt` to prevent breaking changes
- Test package updates in isolation before committing
- Monitor Python 3.13 compatibility as ecosystem matures

### macOS Considerations
- Homebrew Python installations work reliably
- System Python (3.9.x) may have compatibility issues
- SSL certificate issues common; use `--trusted-host` as needed

### Performance
- Python 3.13 provides performance improvements
- numpy/pandas operations compile for ARM64
- Dataset caching reduces network dependency for repeated runs

## Troubleshooting

### Common Errors

**`mmap failed with errno=4`**
- Binary extension corruption
- Solution: Rebuild virtual environment

**`SSLCertVerificationError`**
- macOS SSL certificate issues
- Solution: Use `--trusted-host` flags

**`NameResolutionError` for huggingface.co**
- Network connectivity issues
- ARC loader will use cached data if available

**Import errors after package updates**
- Incompatible package versions
- Check `requirements.txt` and rebuild if needed

## File Structure
```
SyntraCMT/
├── .venv/                    # Active virtual environment
├── .venv.bak/               # Backup of previous environment
├── requirements.txt         # All Python dependencies
└── VENV_SETUP.md           # This documentation
```
