"""Allow only legacy files and content-addressed standard preview releases."""
import re
from package import FILES

STANDARD_PATTERN=re.compile(r'standard-v1/[0-9a-f]{64}/(?:profiles/(?:manifest\.json|config\.json|LICENSE|README\.md|block-[1-5]\.(?:xml|bin))|evidence/(?:parity\.json|protocol-parity\.xml|provenance\.json|manifest-sha256\.txt))')


def is_standard_file(name):
    return bool(STANDARD_PATTERN.fullmatch(name))


def validate_remote_inventory(names):
    allowed=FILES|{'SHA256SUMS','.gitattributes'}
    if any(name not in allowed and not is_standard_file(name) for name in names):
        raise ValueError('remote repository contains unexpected files; refusing to publish')
