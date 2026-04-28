#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONF_FILE="${SCRIPT_DIR}/odm.conf"

if [[ ! -f "${CONF_FILE}" ]]; then
  echo "Missing config file: ${CONF_FILE}" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "${CONF_FILE}"

usage() {
  cat <<'EOF'
Usage:
  ./run_odm.sh --list
  ./run_odm.sh <project_name> [extra_odm_args...]

Project structure required under DATA_ROOT:
  DATA_ROOT/<project_name>/images/*.jpg
or:
  DATA_ROOT/<project_name>/*.jpg

Examples:
  ./run_odm.sh --list
  ./run_odm.sh mission_01
  ./run_odm.sh mission_01 --dsm --dtm --rerun-all
EOF
}

list_projects() {
  if [[ ! -d "${DATA_ROOT}" ]]; then
    echo "DATA_ROOT not found: ${DATA_ROOT}" >&2
    exit 1
  fi

  echo "DATA_ROOT: ${DATA_ROOT}"
  echo "Projects with images:"
  local found=0
  while IFS= read -r project; do
    found=1
    basename "${project}"
  done < <(
    find "${DATA_ROOT}" -mindepth 1 -maxdepth 1 -type d | while IFS= read -r p; do
      if [[ -d "${p}/images" ]]; then
        echo "${p}"
      elif [[ "$(find "${p}" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.tif' -o -iname '*.tiff' \) | wc -l)" -gt 0 ]]; then
        echo "${p}"
      fi
    done | sort
  )

  if [[ "${found}" -eq 0 ]]; then
    echo "(none found)"
  fi
}

prepare_images_dir_if_needed() {
  if [[ -d "${images_dir}" ]]; then
    return 0
  fi

  # ODM expects <project>/images; create symlinks instead of copying files.
  local image_count
  image_count="$(find "${project_dir}" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.tif' -o -iname '*.tiff' \) | wc -l)"
  if [[ "${image_count}" -eq 0 ]]; then
    return 1
  fi

  mkdir -p "${images_dir}"
  while IFS= read -r src; do
    local base
    base="$(basename "${src}")"
    ln -sfn "../${base}" "${images_dir}/${base}"
  done < <(find "${project_dir}" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.tif' -o -iname '*.tiff' \) | sort)

  echo "Prepared ${images_dir} with ${image_count} symlinked images."
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if [[ "${1:-}" == "--list" ]]; then
  list_projects
  exit 0
fi

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

project_name="$1"
shift || true

project_dir="${DATA_ROOT}/${project_name}"
images_dir="${project_dir}/images"

if [[ ! -d "${images_dir}" ]]; then
  if ! prepare_images_dir_if_needed; then
    echo "No images found in project: ${project_dir}" >&2
    echo "Expected ${images_dir} or image files directly in ${project_dir}" >&2
    echo "Run './run_odm.sh --list' to discover valid project names." >&2
    exit 1
  fi
fi

echo "Running ODM..."
echo "  Image: ${ODM_IMAGE}"
echo "  Data root: ${DATA_ROOT}"
echo "  Project: ${project_name}"
echo "  Default args: ${ODM_DEFAULT_ARGS}"
if [[ $# -gt 0 ]]; then
  echo "  Extra args: $*"
fi

docker run --rm -ti \
  -v "${DATA_ROOT}:/datasets" \
  "${ODM_IMAGE}" \
  --project-path /datasets \
  "${project_name}" \
  ${ODM_DEFAULT_ARGS} \
  "$@"
