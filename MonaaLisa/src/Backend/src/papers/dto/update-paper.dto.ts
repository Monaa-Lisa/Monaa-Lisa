import { PartialType } from '@nestjs/mapped-types';
import { CreatePaperDto } from './create-paper.dto';

export class UpdatePaperDto extends PartialType(CreatePaperDto) {}
