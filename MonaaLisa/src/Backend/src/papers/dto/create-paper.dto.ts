import {
  IsISO8601,
  IsNotEmpty,
  IsOptional,
  IsArray,
  IsString,
  IsUrl,
} from 'class-validator';

export class CreatePaperDto {
  @IsNotEmpty()
  @IsString()
  entry_id!: string;

  @IsNotEmpty()
  @IsString()
  title!: string;

  @IsNotEmpty()
  @IsArray()
  @IsString({ each: true })
  authors!: string[];

  @IsNotEmpty()
  @IsString()
  summary!: string;

  // ISO-8601 String; im Service in Date konvertieren
  @IsOptional()
  @IsISO8601()
  published?: string;

  @IsOptional()
  @IsString()
  category?: string;

  @IsOptional()
  @IsUrl()
  url?: string;

  // unique
  @IsNotEmpty()
  @IsString()
  hash!: string;

  // JSON-Felder optional (class-validator kann JSON nicht sauber prüfen)
  @IsOptional()
  citations?: unknown;

  @IsOptional()
  tsne?: unknown;
}
