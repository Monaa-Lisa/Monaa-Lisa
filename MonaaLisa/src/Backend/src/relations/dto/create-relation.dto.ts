import { IsString, IsNumber, Min, Max } from 'class-validator';

/**
 * DTO für das Anlegen einer Relation zwischen zwei Papers.
 */
export class CreateRelationDto {
  @IsString()
  source_id: string;

  @IsString()
  target_id: string;

  @IsNumber()
  @Min(0)
  @Max(1)
  confidence: number;
}
