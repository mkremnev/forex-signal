FROM cockpithq/cockpit:core-2.12.1-unit

# Install PHP Redis extension
# Cockpit core image is based on Alpine with PHP
USER root

RUN apk add --no-cache \
    php82-pecl-redis \
    && rm -rf /var/cache/apk/*

# Copy configuration
COPY ./config/ /var/www/html/config/

# Copy Redis integration addon
COPY ./addons/ /var/www/html/addons/

# Copy storage (if needed for initial data)
COPY ./storage/ /var/www/html/storage/

# Ensure proper permissions
RUN chown -R unit:unit /var/www/html/config \
    && chown -R unit:unit /var/www/html/addons \
    && chown -R unit:unit /var/www/html/storage

USER unit

EXPOSE 8080