import { Controller, Get } from '@nestjs/common';
import { CategoriesService } from './categories.service';

@Controller('categories')
export class CategoriesController {
  constructor(private readonly categories: CategoriesService) {}

  /**
   * GET /categories
   * Papers of the dataset per arXiv category: [{ id, papers, primary }]
   */
  @Get()
  counts() {
    return this.categories.counts();
  }
}
