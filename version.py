# version.py
__version__ = "3.2.0-RU-YooKassa"

def is_version_less(version1, version2):
    """Compare two version strings"""
    v1_parts = [int(x) for x in version1.split('.')]
    v2_parts = [int(x) for x in version2.split('.')]

    for i in range(max(len(v1_parts), len(v2_parts))):
        v1 = v1_parts[i] if i < len(v1_parts) else 0
        v2 = v2_parts[i] if i < len(v2_parts) else 0
        if v1 < v2:
            return True
        elif v1 > v2:
            return False
    return False
