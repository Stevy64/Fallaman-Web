#!/bin/sh
# Met à jour Fallaman sur le cluster déjà en place.
# fallaman-deploy         image GHCR (choix A, etape 4)
# fallaman-deploy local   image construite sur le VPS (choix B, etape 4)
# La migration passe avant le redémarrage. Si elle échoue, les pods en service restent.
set -eu
MODE=${1:-ghcr}
NS=fallaman
DIR=/srv/fallaman/Fallaman/deploy/k8s
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cp "$DIR"/*.yaml "$WORK"/
if [ "$MODE" = local ]; then
  sed -i \
    -e 's|ghcr.io/stevy64/fallaman:main|docker.io/library/fallaman:1|g' \
    -e 's|imagePullPolicy: Always|imagePullPolicy: Never|g' \
    "$WORK"/*.yaml
fi
DIR=$WORK
kubectl apply -f "$DIR/redis.yaml" -f "$DIR/volumes.yaml"
kubectl -n "$NS" rollout status deployment/redis --timeout=180s
kubectl -n "$NS" delete job fallaman-migrate --ignore-not-found
kubectl apply -f "$DIR/migrate.yaml"
kubectl -n "$NS" wait --for=condition=complete job/fallaman-migrate --timeout=180s
kubectl apply -f "$DIR/web.yaml" -f "$DIR/celery.yaml"
kubectl -n "$NS" rollout restart deployment/fallaman-web deployment/fallaman-worker deployment/fallaman-beat
kubectl -n "$NS" rollout status deployment/fallaman-web --timeout=180s
kubectl -n "$NS" rollout status deployment/fallaman-worker --timeout=180s
kubectl -n "$NS" rollout status deployment/fallaman-beat --timeout=180s
