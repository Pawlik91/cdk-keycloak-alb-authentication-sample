FROM jboss/keycloak:9.0.3

ENV KEYCLOAK_IMPORT="/tmp/realm.json"
ENV KEYCLOAK_USER="admin"
ENV KEYCLOAK_PASSWORD="admin"

COPY --chown=jboss:jboss realm.json /tmp/realm.json