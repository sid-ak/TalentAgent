import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService } from './services/api.service';
import { SystemStatus } from './models/talentagent.models';
import { NavbarComponent } from './components/navbar/navbar.component';
import { ProfileViewComponent } from './views/profile-view/profile-view.component';
import { ComposeViewComponent } from './views/compose-view/compose-view.component';
import { GraphViewComponent } from './views/graph-view/graph-view.component';
import { GuardrailsViewComponent } from './views/guardrails-view/guardrails-view.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    CommonModule,
    NavbarComponent,
    ProfileViewComponent,
    ComposeViewComponent,
    GraphViewComponent,
    GuardrailsViewComponent,
  ],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App implements OnInit {
  activeTab = signal<string>('compose');
  selectedProfileId = signal<string>('profile_a');
  status = signal<SystemStatus | null>(null);
  isConnected = signal<boolean>(false);

  constructor(private apiService: ApiService) {}

  async ngOnInit(): Promise<void> {
    const isConn = await this.apiService.checkHealth();
    this.isConnected.set(isConn);
    const stat = await this.apiService.getStatus();
    this.status.set(stat);
  }

  onTabChange(tab: string): void {
    this.activeTab.set(tab);
  }

  onProfileSelected(profileId: string): void {
    this.selectedProfileId.set(profileId);
  }
}
