/**
 * Nico August 2025
 */
import { ValidationPipe } from '@nestjs/common';
import { NestFactory } from '@nestjs/core';
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
  const app = await NestFactory.create(AppModule);
  // Runs the class-validator rules on every DTO and fills in their defaults
  app.useGlobalPipes(new ValidationPipe({ transform: true, whitelist: true }));
  const env = readEnv();
  const port = Number(env.PORT ?? 3000);
  const allowedOrigins = (env.FRONTEND_ORIGIN ?? 'http://localhost:5173')
    .split(',')
    .map((origin) => origin.trim())
    .filter(Boolean);

  app.enableCors({
    origin(origin, callback) {
      if (!origin || allowedOrigins.includes(origin)) {
        callback(null, true);
        return;
      }
      callback(new Error(`Origin ${origin} not allowed by CORS`));
    },
    credentials: true,
  });

  await app.listen(port);
}
void bootstrap();
