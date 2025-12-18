FROM cockpithq/cockpit:core-2.12.1-unit

# PHP Redis extension is already included in the base image

# Copy configuration
COPY ./config/ /var/www/html/config/

# Copy Redis integration addon
COPY ./addons/ /var/www/html/addons/

# Copy storage (if needed for initial data)
COPY ./storage/ /var/www/html/storage/

# Ensure proper permissions for unit user
RUN chown -R unit:unit /var/www/html/config \
    && chown -R unit:unit /var/www/html/addons \
    && chown -R unit:unit /var/www/html/storage

EXPOSE 80
