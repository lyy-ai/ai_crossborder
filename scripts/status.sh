#!/bin/bash
curl -s -m 5 http://127.0.0.1:10046/api/health/services 2>/dev/null || echo '{"backend":"down"}'
echo
ss -tlnp 2>/dev/null | grep -E "1004[5-9]|10050" | awk '{print $4}' | sort
