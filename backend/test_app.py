import unittest
from unittest.mock import patch, MagicMock
import bcrypt
from elevateiq_app import create_app

class ElevateIQTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    @patch('elevateiq_app.routes.auth_routes.get_connection')
    def test_register_success(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        # Simulating that email is not registered
        mock_cursor.fetchone.return_value = None
        
        response = self.client.post('/register', json={
            'name': 'Test User',
            'email': 'test@example.com',
            'password': 'password123'
        })
        
        self.assertEqual(response.status_code, 201)
        self.assertIn(b'Registration successful', response.data)

    @patch('elevateiq_app.routes.auth_routes.get_connection')
    def test_register_duplicate(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        # Simulating email already exists
        mock_cursor.fetchone.return_value = (1,)
        
        response = self.client.post('/register', json={
            'name': 'Test User',
            'email': 'test@example.com',
            'password': 'password123'
        })
        
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'Email already registered', response.data)

    @patch('elevateiq_app.routes.auth_routes.get_connection')
    def test_login_success(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        hashed_pw = bcrypt.hashpw(b'password123', bcrypt.gensalt()).decode('utf-8')
        # Simulate user record found directly in users table
        mock_cursor.fetchone.side_effect = [
            None, # Not employee
            None, # Not client
            {
                'id': 1,
                'name': 'Test User',
                'email': 'test@example.com',
                'password': hashed_pw,
                'role': 'candidate'
            }
        ]
        
        response = self.client.post('/login', json={
            'email': 'test@example.com',
            'password': 'password123'
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Login successful', response.data)
        
    @patch('elevateiq_app.routes.auth_routes.get_connection')
    def test_login_invalid(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        # Simulate user not found in DB
        mock_cursor.fetchone.return_value = None
        
        response = self.client.post('/login', json={
            'email': 'test@example.com',
            'password': 'wrongpassword'
        })
        
        self.assertEqual(response.status_code, 401)
        self.assertIn(b'Invalid credentials', response.data)

    @patch('elevateiq_app.routes.auth_routes.get_connection')
    @patch('elevateiq_app.routes.auth_routes.get_current_user')
    def test_get_profile_unauthorized(self, mock_get_user, mock_get_conn):
        mock_get_user.return_value = None
        response = self.client.get('/profile')
        self.assertEqual(response.status_code, 401)

    @patch('elevateiq_app.routes.auth_routes.get_connection')
    @patch('elevateiq_app.routes.auth_routes.get_current_user')
    def test_get_profile_success(self, mock_get_user, mock_get_conn):
        mock_get_user.return_value = {
            'id': 1,
            'name': 'Candidate User',
            'email': 'candidate@example.com',
            'role': 'candidate'
        }
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        mock_cursor.fetchone.return_value = {
            'id': 1,
            'name': 'Candidate User',
            'email': 'candidate@example.com',
            'role': 'candidate'
        }
        
        response = self.client.get('/profile')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'candidate@example.com', response.data)

    @patch('elevateiq_app.routes.crm_routes.get_connection')
    @patch('elevateiq_app.routes.crm_routes.get_current_user')
    def test_get_crm_clients_success(self, mock_get_user, mock_get_conn):
        # Admin gets CRM clients
        mock_get_user.return_value = {
            'id': 1,
            'name': 'Admin User',
            'email': 'admin@example.com',
            'role': 'admin'
        }
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        mock_cursor.fetchone.return_value = None
        mock_cursor.fetchall.return_value = [
            {
                'id': 1,
                'company_name': 'Acme Corp',
                'contact_name': 'John Doe',
                'email': 'john@acme.com',
                'phone_number': '123456789',
                'deal_size': 5000.0,
                'status': 'Lead'
            }
        ]
        
        response = self.client.get('/crm/clients')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Acme Corp', response.data)

    @patch('elevateiq_app.routes.leaves.get_connection')
    @patch('elevateiq_app.routes.leaves.get_current_user')
    def test_apply_leave_success(self, mock_get_user, mock_get_conn):
        mock_get_user.return_value = {
            'id': 2,
            'name': 'Employee User',
            'email': 'emp@example.com',
            'role': 'employee',
            'emp_db_id': 10
        }
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock employee leave balance
        mock_cursor.fetchone.return_value = {
            'id': 10,
            'casual_leave': 10,
            'sick_leave': 5
        }
        
        response = self.client.post('/leaves', json={
            'leave_type': 'Casual',
            'start_date': '2026-07-10',
            'end_date': '2026-07-12',
            'reason': 'Vacation'
        })
        
        self.assertEqual(response.status_code, 201)
        self.assertIn(b'Leave application submitted successfully', response.data)

    @patch('elevateiq_app.routes.auth_routes.get_connection')
    @patch('elevateiq_app.auth.get_current_user')
    def test_get_designations(self, mock_get_user, mock_get_conn):
        mock_get_user.return_value = {
            'id': 1,
            'name': 'Admin User',
            'email': 'admin@example.com',
            'role': 'admin'
        }
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        mock_cursor.fetchall.return_value = [
            {'id': 1, 'name': 'HR Manager'},
            {'id': 2, 'name': 'Team Leader'}
        ]
        
        response = self.client.get('/designations')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'HR Manager', response.data)

    @patch('elevateiq_app.routes.auth_routes.get_connection')
    @patch('elevateiq_app.auth.get_current_user')
    def test_create_designation_success(self, mock_get_user, mock_get_conn):
        mock_get_user.return_value = {
            'id': 1,
            'name': 'Admin User',
            'email': 'admin@example.com',
            'role': 'admin'
        }
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        mock_cursor.fetchone.return_value = {'id': 3, 'name': 'Systems Engineer'}
        
        response = self.client.post('/designations', json={'name': 'Systems Engineer'})
        self.assertEqual(response.status_code, 201)
        self.assertIn(b'Systems Engineer', response.data)

if __name__ == '__main__':
    unittest.main()
