#!/bin/bash
set -e

NAME="Audio Tools"
EMAIL="danielfcollier@gmail.com"
OUT_DIR="$(dirname "$0")"
PARAMS=$(mktemp)

cat > "$PARAMS" <<HEREDOC
Key-Type: RSA
Key-Length: 4096
Name-Real: ${NAME}
Name-Email: ${EMAIL}
Expire-Date: 0
%no-protection
HEREDOC

echo "Generating GPG key for '${NAME} <${EMAIL}>'..."
gpg --batch --gen-key "$PARAMS"
rm -f "$PARAMS"

KEY_ID=$(gpg --list-secret-keys --keyid-format LONG "${EMAIL}" \
  | grep '^sec' | awk '{print $2}' | cut -d'/' -f2 | head -1)

echo "Key ID: ${KEY_ID}"

gpg --armor --export "${KEY_ID}" > "${OUT_DIR}/audio-tools.gpg.pub"
gpg --armor --export-secret-keys "${KEY_ID}" > "${OUT_DIR}/audio-tools.gpg.key"
chmod 600 "${OUT_DIR}/audio-tools.gpg.key"

echo ""
echo "Generated:"
echo "  ${OUT_DIR}/audio-tools.gpg.pub  (upload to S3 / share publicly)"
echo "  ${OUT_DIR}/audio-tools.gpg.key  (keep secret)"
echo ""
echo "Add to your .env:"
echo "  GPG_KEY_ID=${KEY_ID}"
echo "  GPG_KEY_FILE=${OUT_DIR}/audio-tools.gpg.key"
echo "  GPG_PUBKEY_FILE=${OUT_DIR}/audio-tools.gpg.pub"
