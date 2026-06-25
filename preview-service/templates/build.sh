#!/bin/bash
# Build E2B custom templates and output template IDs.
# Run once: bash preview-service/templates/build.sh
# Then add the printed IDs to .env as E2B_TEMPLATE_NEXTJS, E2B_TEMPLATE_PYTHON, E2B_TEMPLATE_DJANGO.
#
# Prerequisites:
#   pip install e2b-cli  (or npm install -g @e2b/cli)
#   e2b auth login       (authenticates with E2B_API_KEY)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

build_template() {
    local name="$1"
    local dockerfile="$2"
    echo ""
    echo "Building E2B template: $name ..."
    id=$(e2b template build \
        --name "$name" \
        --dockerfile "$SCRIPT_DIR/$dockerfile" \
        --output-format json 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('templateID',''))")
    if [ -n "$id" ]; then
        echo "  Template ID: $id"
        echo "  -> Add to .env: E2B_TEMPLATE_$(echo $name | tr '[:lower:]-' '[:upper:]_' | sed 's/AINERON_//')=$id"
    else
        echo "  Build failed or no ID returned — check e2b CLI output above."
    fi
}

build_template "aineron-python" "python.Dockerfile"
build_template "aineron-django" "django.Dockerfile"
build_template "aineron-nextjs" "nextjs.Dockerfile"

echo ""
echo "Done. Add the template IDs above to .env, then restart preview-service."
