# Usar una imagen base de Node.js
FROM node:14

# Establecer el directorio de trabajo
WORKDIR /code/frontend

# Copiar el código del frontend
COPY ./app/frontend /code/frontend

# Instalar dependencias de Node.js
RUN npm install

# Exponer el puerto 3000
EXPOSE 3000

# Comando por defecto para ejecutar la aplicación
CMD ["npm", "start"]
