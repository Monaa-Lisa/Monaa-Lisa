/**
 * Nico August 2025
 * Das hier ist ein Unit Test des Controllers. Es werden nur die Komponenten der Klasse
 * isoliert getestet, aber es werden keine Web-Requests simuliert
 */
import { Test, TestingModule } from '@nestjs/testing';
import { AppController } from './app.controller';
import { AppService } from './app.service';

describe('AppController', () => {
  let appController: AppController;

  beforeEach(async () => {
    const app: TestingModule = await Test.createTestingModule({
      controllers: [AppController],
      providers: [AppService],
    }).compile();

    appController = app.get<AppController>(AppController);
  });

  describe('root', () => {
    it('should return "Hello from MonaaLisa!"', () => {
      expect(appController.getHello()).toBe('Hello from MonaaLisa!');
    });
  });
});
