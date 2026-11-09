/**
 * Nico August 2025
 */
import { ValidationPipe } from '@nestjs/common';
import { NestFactory } from '@nestjs/core';
import { NestExpressApplication } from '@nestjs/platform-express';
import compression from 'compression';
import helmet from 'helmet';
import { AppModule } from './app.module';

type EnvAccessor = {
  process?: {
    env?: Record<string, string | undefined>;
  };
};

function readEnv() {
  return (globalThis as EnvAccessor).process?.env ?? {};
}

async function bootstrap() {
  const env = readEnv();
  const app = await NestFactory.create<NestExpressApplication>(AppModule);
  app.use(helmet());
  // the paper lists are JSON of several hundred kB, gzip takes two thirds off
  app.use(compression());
  // Behind a reverse proxy (Caddy/nginx) the rate limiter needs the client IP
  // from X-Forwarded-For. Set TRUST_PROXY to the number of proxies in front.
  if (env.TRUST_PROXY) {
    app.set('trust proxy', Number(env.TRUST_PROXY));
  }
  // Runs the class-validator rules on every DTO and fills in their defaults
  app.useGlobalPipes(new ValidationPipe({ transform: true, whitelist: true }));
  const port = Number(env.PORT ?? 3000);
  const allowedOrigins = (env.FRONTEND_ORIGIN ?? 'http://localhost:5173')
    .split(',')
    .map((origin) => origin.trim())
    .filter(Boolean);

  // Only the frontend's own origins get the CORS headers. A request from
  // another origin is answered without them, so a browser there discards the
  // answer; the API is public and read only, there is nothing to protect by
  // failing the request itself. No cookies are used, hence no credentials.
  app.enableCors({
    origin(origin, callback) {
      callback(null, !origin || allowedOrigins.includes(origin));
    },
  });

  await app.listen(port);
}
void bootstrap();
