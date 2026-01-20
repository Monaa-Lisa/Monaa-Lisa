import { IsNotEmpty, IsObject, IsString } from 'class-validator';

export class CreateReferenceDto {
  @IsNotEmpty()
  @IsString()
  belonging_paper_entry_id!: string;

  @IsNotEmpty()
  @IsObject()
  semanticscholar_obj!: Record<string, any>;
}

